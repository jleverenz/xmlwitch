from __future__ import with_statement
from StringIO import StringIO
from xml.sax import saxutils
from keyword import kwlist as PYTHON_KWORD_LIST

__all__ = ['Builder', 'Element']
__license__ = 'BSD'
__version__ = '0.2.1'
__author__ = "Jonas Galvez <http://jonasgalvez.com.br/>"
__contributors__ = ["bbolli <http://github.com/bbolli/>",
                    "masklinn <http://github.com/masklinn/>"]

class Builder:

    def __init__(self, encoding='utf-8', indent=' '*2, version=None):
        self._document = StringIO()
        self._encoding = encoding
        self._indent = indent
        self._indentation = 0
        if version is not None:
            self.write('<?xml version="%s" encoding="%s"?>\n' % (
                version, encoding
            ))
        self._sm = XmlStateMachine(self)

    def __getattr__(self, name):
        return Element(name, self._sm)

    def __str__(self):
        self._sm.exit_sm()
        return self._document.getvalue().encode(self._encoding).strip()

    def __unicode__(self):
        self._sm.exit_sm()
        return self._document.getvalue().decode(self._encoding).strip()

    def write(self, content):
        """Write raw content to the document"""
        if type(content) is not unicode:
            content = content.decode(self._encoding)
        self._document.write('%s' % content)

    def write_escaped(self, content):
        """Write escaped content to the document"""
        self.write(saxutils.escape(content))

    def write_indented(self, content):
        """Write indented content to the document"""
        self.write('%s%s' % (self._indent * self._indentation, content))

builder = Builder # 0.1 backward compatibility

# State machine to track when xml building state, used to correctly close tags
# based on potential future xml content. e.g. using /> to close a tag might not
# possible if the next call enters context to build child xml nodes.

class XmlStateMachine:
    CALL_EVENT = 1
    ENTER_EVENT = 2
    EXIT_EVENT = 3

    def __init__(self, builder):
        # called | entered
        self.state = 00
        self.stack = []
        self.prev = None
        self.curr = None
        self.needs_indent = False
        self.builder = builder

    def exit_sm(self):
        self.prev = self.curr
        if self.state == 2:
            self.brace_close()

    def handle_event(self, event, curr):
        self.prev = self.curr
        self.curr = curr

        if self.state == 00:
            if event == XmlStateMachine.CALL_EVENT:
                self.emit_tag()
                self.state = 2
            elif event == XmlStateMachine.ENTER_EVENT:
                self.stack.append(self.curr)
                self.emit_tag()
                self.needs_indent = True
                self.state = 1
            else: # exit
                self.pop_stack_with_close()
                self.state = 0
        elif self.state == 01:
            if event == XmlStateMachine.CALL_EVENT:
                self.close()
                self.emit_tag()
                self.state = 2
            elif event == XmlStateMachine.EXIT_EVENT:
                self.brace_close()
                self.pop_stack()
                self.state = 0
            else:
                exit("bad event for state 01")
        elif self.state == 02:
            if event == XmlStateMachine.CALL_EVENT:
                self.brace_close()
                self.emit_tag()
                # keep state
            elif event == XmlStateMachine.ENTER_EVENT:
                self.stack.append(self.curr)
                if self.prev == self.curr:
                    self.state = 3
                else:
                    self.brace_close()
                    self.emit_tag()
                    self.state = 1
                self.needs_indent = True
            else: # exit
                self.brace_close()
                self.pop_stack_with_close()
                self.state = 0
        elif self.state == 03:
            if event == XmlStateMachine.CALL_EVENT:
                self.close()
                self.emit_tag()
                self.state = 2
            elif event == XmlStateMachine.EXIT_EVENT:
                self.brace_close()
                self.pop_stack()
                self.state = 0
            else: # enter
                exit("bad event for state 03")

    def emit_tag(self):
        if self.curr.value:
            self.text = "<%s%s>%s" % (self.curr.name,
                                      self.curr._serialized_attrs(),
                                      self.curr.value)
        else:
            self.text = "<%s%s" % (self.curr.name, self.curr._serialized_attrs())

    def brace_close(self):
        if self.prev.value:
            self.text += "</%s>\n" % (self.prev.name)
        else:
            self.text += " />\n"
        self.builder.write_indented( self.text )
        if self.needs_indent:
            self.builder._indentation += 1
            self.needs_indent = False

    def close(self):
        if self.prev.value:
            self.text +=  "\n"
        else:
            self.text +=  ">\n"
        self.builder.write_indented( self.text )
        if self.needs_indent:
            self.builder._indentation += 1
            self.needs_indent = False

    def pop_stack(self):
        self.builder._indentation -= 1
        return self.stack.pop()

    def pop_stack_with_close(self):
        popped = self.pop_stack()
        self.builder.write_indented( "</%s>\n" % (popped.name))


class Element:

    PYTHON_KWORD_MAP = dict([(k + '_', k) for k in PYTHON_KWORD_LIST])

    def __init__(self, name, xml_state_machine):
        self.name = self._nameprep(name)
        self.xml_sm = xml_state_machine
        self.attributes = {}
        self.value = None

    def __enter__(self):
        """Add a parent element to the document"""
        self.xml_sm.handle_event(XmlStateMachine.ENTER_EVENT, self)
        return self

    def __exit__(self, type, value, tb):
        """Add close tag to current parent element"""
        self.xml_sm.handle_event(XmlStateMachine.EXIT_EVENT, self)

    def __call__(*args, **kargs):
        """Add a child element to the document"""
        self = args[0]

        self.attributes.update(kargs)

        value = args[1] if len(args) > 1 else None

        if value:
            value = saxutils.escape(value)

        self.value = value
        self.xml_sm.handle_event(XmlStateMachine.CALL_EVENT, self)
        return self

    def _serialized_attrs(self):
        """Serialize attributes for element insertion"""
        serialized = []
        for attr, value in self.attributes.items():
            serialized.append(' %s=%s' % (
                self._nameprep(attr), saxutils.quoteattr(value)
            ))
        return ''.join(serialized)

    def _nameprep(self, name):
        """Undo keyword and colon mangling"""
        name = Element.PYTHON_KWORD_MAP.get(name, name)
        return name.replace('__', ':')
