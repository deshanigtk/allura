import logging

from ming import schema as S
from ming.orm import MappedClass
from ming.orm import FieldProperty, RelationProperty, ForeignIdProperty

from pylons import request, c

from allura.lib import plugin

from .session import main_orm_session
from .filesystem import File

log = logging.getLogger(__name__)

class NeighborhoodFile(File):
    class __mongometa__:
        session = main_orm_session
    neighborhood_id=FieldProperty(S.ObjectId)

class Neighborhood(MappedClass):
    '''Provide a grouping of related projects.

    url_prefix - location of neighborhood (may include scheme and/or host)
    css - block of CSS text to add to all neighborhood pages
    acl - list of user IDs who have rights to perform ops on neighborhood.  Empty
        acl implies that any authenticated user can perform the op
        'read' - access the neighborhood (usually [ User.anonymous()._id ])
        'create' - create projects within the neighborhood (open neighborhoods
            will typically have this empty)
        'moderate' - invite projects into the neighborhood, evict projects from
            the neighborhood
        'admin' - update neighborhood ACLs, acts as a superuser with all
            permissions in neighborhood projects
    '''
    class __mongometa__:
        session = main_orm_session
        name = 'neighborhood'

    _id = FieldProperty(S.ObjectId)
    name = FieldProperty(str)
    url_prefix = FieldProperty(str) # e.g. http://adobe.openforge.com/ or projects/
    shortname_prefix = FieldProperty(str, if_missing='')
    css = FieldProperty(str, if_missing='')
    homepage = FieldProperty(str, if_missing='')
    acl = FieldProperty({
            'read':[S.ObjectId],      # access neighborhood at all
            'create':[S.ObjectId],    # create project in neighborhood
            'moderate':[S.ObjectId],    # invite/evict projects
            'admin':[S.ObjectId],  # update ACLs
            })
    redirect = FieldProperty(str, if_missing='')
    projects = RelationProperty('Project')
    allow_browse = FieldProperty(bool, if_missing=True)
    site_specific_html = FieldProperty(str, if_missing='')

    def url(self):
        url = self.url_prefix
        if url.startswith('//'):
            try:
                return request.scheme + ':' + url
            except TypeError: # pragma no cover
                return 'http:' + url
        else:
            return url

    def register_project(self, shortname, user=None, user_project=False):
        '''Register a new project in the neighborhood.  The given user will
        become the project's superuser.  If no user is specified, c.user is used.
        '''
        provider = plugin.ProjectRegistrationProvider.get()
        return provider.register_project(self, shortname, user or getattr(c,'user',None), user_project)

    def bind_controller(self, controller):
        from allura.controllers.project import NeighborhoodController
        controller_attr = self.url_prefix[1:-1]
        setattr(controller, controller_attr, NeighborhoodController(
                self.name, self.shortname_prefix))

    @property
    def icon(self):
        return NeighborhoodFile.query.get(neighborhood_id=self._id)

