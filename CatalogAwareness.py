# catalog awareness for zwiki pages
# originally based on Casey Duncan's DTMLDocumentExt 0.1

import string

from AccessControl import getSecurityManager, ClassSecurityInfo
from Globals import InitializeClass

import Permissions
from Utils import BLATHER,formattedTraceback


class CatalogAwareness:
    """
    Holds most of ZWikiPage's catalog awareness code.  Similar to Zope's
    or CMF's catalog awareness with a little extra behaviour.
    """
    security = ClassSecurityInfo()

    NOT_CATALOGED=0
    _properties=(
        {'id':'NOT_CATALOGED', 'type': 'boolean', 'mode': 'w'},
        )

    security.declareProtected(Permissions.View, 'isCatalogable')
    def isCatalogable(self):
        return not getattr(self, 'NOT_CATALOGED', 0)

    def catalog(self):
        """
        Return the catalog object used by this page, if any.

        By default, Zwiki looks for an object named 'Catalog' in this wiki
        folder (will not acquire) or a 'portal_catalog' (can acquire).

        If a SITE_CATALOG property exists (can acquire), Zwiki will look
        for an object by that name (can acquire); if no such object
        exists, or SITE_CATALOG is blank, no catalog will be used.
        """
        folder = self.folder()
        folderaqbase = getattr(folder,'aq_base',
                               folder) # make tests work
        if not hasattr(self,'SITE_CATALOG'):
            if hasattr(folderaqbase,'Catalog'):
                return folder.Catalog
            else:
                return getattr(folder,'portal_catalog',None)
        else:
            return getattr(folder,self.SITE_CATALOG,None)

    security.declareProtected(Permissions.View, 'hasCatalog')
    def hasCatalog(self):
        """Is this page keeping itself indexed in a catalog ?"""
        return self.catalog() != None

    security.declareProtected(Permissions.View, 'catalogid')
    def catalogId(self):
        """
        Give the id of the catalog used by this page, or "NONE".

        Should be useful for troubleshooting. 
        """
        if self.hasCatalog(): return self.catalog().getId()
        else: return 'NONE'

    def hasCatalogIndexesMetadata(self,indexesAndMetadata):
        """
        Do we have a catalog with these indexes and metadata ?

        It's good to check that an index exists before searching,
        otherwise we'll get the entire catalog contents.
        indexesAndMetadata is two lists of strings, eg:
        (['index1','index2'],['metadata1'])
        """
        catalog = self.catalog()
        if not catalog: return 0
        catalogindexes, catalogmetadata = catalog.indexes(), catalog.schema()
        indexes, metadata = indexesAndMetadata
        for i in indexes:
            if not i in catalogindexes: return 0
        for i in metadata:
            if not i in catalogmetadata: return 0
        return 1

    def searchCatalog(self,**kw):
        """
        Searches this wiki page's catalog if any, passing through arguments.
        """
        if self.hasCatalog(): return self.catalog()(**kw)
        else: return None

    def url(self):
        """Return the absolute object path"""
        return string.join(self.getPhysicalPath(),'/')

    getPath = url

    security.declareProtected(Permissions.View, 'index_object')
    def index_object(self,idxs=[],log=1):
        """Index this page in the wiki's catalog, if any, and log problems.

        Updates only certain indexes, if specified. 
        """
        if self.hasCatalog() and self.isCatalogable():
            if log:
                BLATHER('indexing',self.url(),'in',self.catalog().getId())
            try:
                self.catalog().catalog_object(self,self.url(),idxs,update_metadata=1)
            except:
                BLATHER('failed to index',self.id(),'\n',formattedTraceback())

    def unindex_object(self):
        """Remove this page from the wiki's catalog, if any."""
        if self.hasCatalog():
            self.catalog().unindexObject(self)

    #XXX backwards compatibility
    updateCatalog = reindex_object = index_object 


InitializeClass(CatalogAwareness)


# enable catalog awareness for common ZMI operations - had to be done in
# __init__ because of an import loop
