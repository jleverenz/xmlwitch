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
        self._treebuilder = XmlTreeBuilder()

    def __getattr__(self, name):
        return Element(name, self)
        
    def __getitem__(self, name):
        return Element(name, self)
    
    def __str__(self):
        self._treebuilder.reset()
        self._treebuilder.render(self)
        return self._document.getvalue().encode(self._encoding).strip()
        
    def __unicode__(self):
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
        self.write('%s%s\n' % (self._indent * self._indentation, content))

builder = Builder # 0.1 backward compatibility

class XmlTreeBuilder:

    def __init__(self):
        self.root = []
        self.position = self.root
        self.stack = []
        
    def open_tag(self, tag, attributes, text, with_block=False):
        if len(self.stack) > 0 and not self.stack[-1][1]:
            self.position = self.stack.pop()[0]  # pop unclosed
        self.stack.append([ self.position, with_block ])
        self.position.append((tag, attributes, text, []))
        self.position = self.position[-1][3]

    def reopen_tag_with_block(self):
        self.stack[-1][1] = True

    def close_tag(self):
        # close last open block
        while len(self.stack) > 1 and not self.stack[-1][1]:
            self.position = self.stack.pop()[0]

        self.position = self.stack.pop()[0]

    def reset(self):
        self.stack = []   # reset stack, effectively closing any remaining open tags
        self.position = self.root

    def render(self, builder):
        self.render_subtree(self.root, builder)

    def render_subtree(self, trees, builder):
        for tree in trees:
            if tree[2] == None and len(tree[3]) == 0:
                builder.write_indented( "<%s%s />" % (tree[0], tree[1]) )
            else:
                if tree[2] != None:
                    if len(tree[3]) == 0:
                        text = "<%s%s>%s</%s>" % (tree[0], tree[1], tree[2], tree[0])
                        builder.write_indented( text )
                    else:
                        builder.write_indented( "<%s%s>%s" % (tree[0], tree[1], tree[2]) )
                        builder._indentation += 1
                        self.render_subtree(tree[3], builder)
                        builder._indentation += -1
                        builder.write_indented( "</%s>" % tree[0] )
                else:
                    builder.write_indented( "<%s%s>" % (tree[0], tree[1]) )
                    builder._indentation += 1
                    self.render_subtree(tree[3], builder)
                    builder._indentation += -1
                    builder.write_indented( "</%s>" % tree[0] )

class Element:
    
    PYTHON_KWORD_MAP = dict([(k + '_', k) for k in PYTHON_KWORD_LIST])
    
    def __init__(self, name, builder):
        self.name = self._nameprep(name)
        self.builder = builder
        self.attributes = {}
        self.opened = False
        self.tree = builder._treebuilder

    def __enter__(self):
        """Add a parent element to the document"""

        if(self.opened):
            self.tree.reopen_tag_with_block()
        else:
            self.tree.open_tag(self.name, self._serialized_attrs(), None, True)
            self.opened = True

        return self
        
    def __exit__(self, type, value, tb):
        """Add close tag to current parent element"""
        self.tree.close_tag()

    def __call__(*args, **kargs):
        """Add a child element to the document"""
        self = args[0]
        self.attributes.update(kargs)

        value = args[1] if len(args) > 1 else None

        if value:
            value = saxutils.escape(value)

        self.opened = True
        self.tree.open_tag(self.name, self._serialized_attrs(), value, False)
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
