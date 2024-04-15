class Linkinfo:
    """linkinfo metadata (which is part of the xml representing a directory)
    """

    def __init__(self):
        """creates an empty linkinfo instance"""
        self.project = None
        self.package = None
        self.xsrcmd5 = None
        self.lsrcmd5 = None
        self.srcmd5 = None
        self.error = None
        self.rev = None
        self.baserev = None

    def read(self, linkinfo_node):
        """read in the linkinfo metadata from the ``<linkinfo>`` element passed as
        elementtree node.
        If the passed element is ``None``, the method does nothing.
        """
        if linkinfo_node is None:
            return
        self.project = linkinfo_node.get('project')
        self.package = linkinfo_node.get('package')
        self.xsrcmd5 = linkinfo_node.get('xsrcmd5')
        self.lsrcmd5 = linkinfo_node.get('lsrcmd5')
        self.srcmd5 = linkinfo_node.get('srcmd5')
        self.error = linkinfo_node.get('error')
        self.rev = linkinfo_node.get('rev')
        self.baserev = linkinfo_node.get('baserev')

    def islink(self):
        """:return: ``True`` if the linkinfo is not empty, otherwise ``False``"""
        if self.xsrcmd5 or self.lsrcmd5 or self.error is not None:
            return True
        return False

    def isexpanded(self):
        """:return: ``True`` if the package is an expanded link"""
        if self.lsrcmd5 and not self.xsrcmd5:
            return True
        return False

    def haserror(self):
        """:return: ``True`` if the link is in error state (could not be applied)"""
        if self.error:
            return True
        return False

    def __str__(self):
        """return an informatory string representation"""
        if self.islink() and not self.isexpanded():
            return 'project %s, package %s, xsrcmd5 %s, rev %s' \
                % (self.project, self.package, self.xsrcmd5, self.rev)
        elif self.islink() and self.isexpanded():
            if self.haserror():
                return 'broken link to project %s, package %s, srcmd5 %s, lsrcmd5 %s: %s' \
                    % (self.project, self.package, self.srcmd5, self.lsrcmd5, self.error)
            else:
                return 'expanded link to project %s, package %s, srcmd5 %s, lsrcmd5 %s' \
                    % (self.project, self.package, self.srcmd5, self.lsrcmd5)
        else:
            return 'None'
