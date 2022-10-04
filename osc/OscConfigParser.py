# Copyright 2008,2009 Marcus Huewe <suse-tux@gmx.de>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License version 2
# as published by the Free Software Foundation;
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA


import configparser


# inspired from http://code.google.com/p/iniparse/ - although their implementation is
# quite different

class ConfigLineOrder:
    """
    A ConfigLineOrder() instance task is to preserve the order of a config file.
    It keeps track of all lines (including comments) in the _lines list. This list
    either contains SectionLine() instances or CommentLine() instances.
    """

    def __init__(self):
        self._lines = []

    def _append(self, line_obj):
        self._lines.append(line_obj)

    def _find_section(self, section):
        for line in self._lines:
            if line.type == 'section' and line.name == section:
                return line
        return None

    def add_section(self, sectname):
        self._append(SectionLine(sectname))

    def get_section(self, sectname):
        section = self._find_section(sectname)
        if section:
            return section
        section = SectionLine(sectname)
        self._append(section)
        return section

    def add_other(self, sectname, line):
        if sectname:
            self.get_section(sectname).add_other(line)
        else:
            self._append(CommentLine(line))

    def keys(self):
        return [i.name for i in self._lines if i.type == 'section']

    def __setitem__(self, key, value):
        section = SectionLine(key)
        self._append(section)

    def __getitem__(self, key):
        section = self._find_section(key)
        if not section:
            raise KeyError()
        return section

    def __delitem__(self, key):
        line = self._find_section(key)
        if not line:
            raise KeyError(key)
        self._lines.remove(line)

    def __iter__(self):
        # return self._lines.__iter__()
        for line in self._lines:
            if line.type == 'section':
                yield line.name


class Line:
    """Base class for all line objects"""

    def __init__(self, name, type):
        self.name = name
        self.type = type


class SectionLine(Line):
    """
    This class represents a [section]. It stores all lines which belongs to
    this certain section in the _lines list. The _lines list either contains
    CommentLine() or OptionLine() instances.
    """

    def __init__(self, sectname):
        super().__init__(sectname, 'section')
        self._lines = []

    def _find(self, name):
        for line in self._lines:
            if line.name == name:
                return line
        return None

    def _add_option(self, optname, value=None, line=None, sep='='):
        if value is None and line is None:
            raise configparser.Error('Either value or line must be passed in')
        elif value and line:
            raise configparser.Error('value and line are mutually exclusive')

        if value is not None:
            line = '%s%s%s' % (optname, sep, value)
        opt = self._find(optname)
        if opt:
            opt.format(line)
        else:
            self._lines.append(OptionLine(optname, line))

    def add_other(self, line):
        self._lines.append(CommentLine(line))

    def copy(self):
        return dict(self.items())

    def items(self):
        return [(i.name, i.value) for i in self._lines if i.type == 'option']

    def keys(self):
        return [i.name for i in self._lines]

    def __setitem__(self, key, val):
        self._add_option(key, val)

    def __getitem__(self, key):
        line = self._find(key)
        if not line:
            raise KeyError(key)
        return str(line)

    def __delitem__(self, key):
        line = self._find(key)
        if not line:
            raise KeyError(key)
        self._lines.remove(line)

    def __str__(self):
        return self.name

    # XXX: needed to support 'x' in cp._sections['sectname']
    def __iter__(self):
        for line in self._lines:
            yield line.name


class CommentLine(Line):
    """Store a commentline"""

    def __init__(self, line):
        super().__init__(line.strip('\n'), 'comment')

    def __str__(self):
        return self.name


class OptionLine(Line):
    """
    This class represents an option. The class' ``name`` attribute is used
    to store the option's name and the "value" attribute contains the option's
    value. The ``frmt`` attribute preserves the format which was used in the configuration
    file.

    Example::

        optionx:<SPACE><SPACE>value
        => self.frmt = '%s:<SPACE><SPACE>%s'
        optiony<SPACE>=<SPACE>value<SPACE>;<SPACE>some_comment
        => self.frmt = '%s<SPACE>=<SPACE><SPACE>%s<SPACE>;<SPACE>some_comment
    """

    def __init__(self, optname, line):
        super().__init__(optname, 'option')
        self.name = optname
        self.format(line)

    def format(self, line):
        mo = configparser.ConfigParser.OPTCRE.match(line.strip())
        key, val = mo.group('option', 'value')
        self.frmt = line.replace(key.strip(), '%s', 1)
        pos = val.find(' ;')
        if pos >= 0:
            val = val[:pos]
        self.value = val
        self.frmt = self.frmt.replace(val.strip(), '%s', 1).rstrip('\n')

    def __str__(self):
        return self.value


class OscConfigParser(configparser.ConfigParser):
    """
    OscConfigParser() behaves like a normal ConfigParser() object. The
    only differences is that it preserves the order+format of configuration entries
    and that it stores comments.
    In order to keep the order and the format it makes use of the ConfigLineOrder()
    class.
    """

    def __init__(self, defaults=None):
        super().__init__(defaults or {}, interpolation=None)
        self._sections = ConfigLineOrder()

    # XXX: unfortunately we have to override the _read() method from the ConfigParser()
    #      class because a) we need to store comments b) the original version doesn't use
    #      the its set methods to add and set sections, options etc. instead they use a
    #      dictionary (this makes it hard for subclasses to use their own objects, IMHO
    #      a bug) and c) in case of an option we need the complete line to store the format.
    #      This all sounds complicated but it isn't - we only needed some slight changes
    def _read(self, fp, fpname):
        """Parse a sectioned setup file.

        The sections in setup file contains a title line at the top,
        indicated by a name in square brackets (`[]'), plus key/value
        options lines, indicated by `name: value' format lines.
        Continuations are represented by an embedded newline then
        leading whitespace.  Blank lines, lines beginning with a '#',
        and just about everything else are ignored.
        """
        cursect = None                            # None, or a dictionary
        optname = None
        lineno = 0
        e = None                                  # None, or an exception
        while True:
            line = fp.readline()
            if not line:
                break
            lineno = lineno + 1
            # comment or blank line?
            if line.strip() == '' or line[0] in '#;':
                self._sections.add_other(cursect, line)
                continue
            if line.split(None, 1)[0].lower() == 'rem' and line[0] in "rR":
                # no leading whitespace
                continue
            # continuation line?
            if line[0].isspace() and cursect is not None and optname:
                value = line.strip()
                if value:
                    #cursect[optname] = "%s\n%s" % (cursect[optname], value)
                    #self.set(cursect, optname, "%s\n%s" % (self.get(cursect, optname), value))
                    if cursect == configparser.DEFAULTSECT:
                        self._defaults[optname] = "%s\n%s" % (self._defaults[optname], value)
                    else:
                        # use the raw value here (original version uses raw=False)
                        self._sections[cursect]._find(optname).value = '%s\n%s' % (self.get(cursect, optname, raw=True), value)
            # a section header or option header?
            else:
                # is it a section header?
                mo = self.SECTCRE.match(line)
                if mo:
                    sectname = mo.group('header')
                    if sectname in self._sections:
                        cursect = self._sections[sectname]
                    elif sectname == configparser.DEFAULTSECT:
                        cursect = self._defaults
                    else:
                        #cursect = {'__name__': sectname}
                        #self._sections[sectname] = cursect
                        self.add_section(sectname)
                        self.set(sectname, '__name__', sectname)
                    # So sections can't start with a continuation line
                    cursect = sectname
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise configparser.MissingSectionHeaderError(fpname, lineno, line)
                # an option line?
                else:
                    mo = self.OPTCRE.match(line)
                    if mo:
                        optname, vi, optval = mo.group('option', 'vi', 'value')
                        if vi in ('=', ':') and ';' in optval:
                            # ';' is a comment delimiter only if it follows
                            # a spacing character
                            pos = optval.find(';')
                            if pos != -1 and optval[pos - 1].isspace():
                                optval = optval[:pos]
                        optval = optval.strip()
                        # allow empty values
                        if optval == '""':
                            optval = ''
                        optname = self.optionxform(optname.rstrip())
                        if cursect == configparser.DEFAULTSECT:
                            self._defaults[optname] = optval
                        else:
                            self._sections[cursect]._add_option(optname, line=line)
                    else:
                        # a non-fatal parsing error occurred.  set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines
                        if not e:
                            e = configparser.ParsingError(fpname)
                        e.append(lineno, repr(line))
        # if any parsing errors occurred, raise an exception
        if e:
            raise e  # pylint: disable-msg=E0702

    def write(self, fp, comments=False):
        """
        write the configuration file. If comments is True all comments etc.
        will be written to fp otherwise the ConfigParsers' default write method
        will be called.
        """
        if comments:
            fp.write(str(self))
            fp.write('\n')
        else:
            super().write(fp)

    def has_option(self, section, option, proper=False, **kwargs):
        """
        Returns True, if the passed section contains the specified option.
        If proper is True, True is only returned if the option is owned by
        this section and not "inherited" from the default.
        """
        if proper:
            return self.optionxform(option) in self._sections[section].keys()
        return super().has_option(section, option, **kwargs)

    # XXX: simplify!
    def __str__(self):
        ret = []
        first = True
        for line in self._sections._lines:
            if line.type == 'section':
                if first:
                    first = False
                else:
                    ret.append('')
                ret.append('[%s]' % line.name)
                for sline in line._lines:
                    if sline.name == '__name__':
                        continue
                    if sline.type == 'option':
                        # special handling for continuation lines
                        val = '\n '.join(sline.value.split('\n'))
                        ret.append(sline.frmt % (sline.name, val))
                    elif str(sline) != '':
                        ret.append(str(sline))
            else:
                ret.append(str(line))
        return '\n'.join(ret)

    def _validate_value_types(self, section="", option="", value=""):
        if not isinstance(section, str):
            raise TypeError("section names must be strings")
        if not isinstance(option, str):
            raise TypeError("option keys must be strings")

# vim: sw=4 et
