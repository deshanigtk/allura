from time import sleep
from datetime import datetime

from pylons import c
from pymongo.errors import OperationFailure

from ming import schema
from ming.orm.mapped_class import MappedClass
from ming.orm.property import FieldProperty, ForeignIdProperty, RelationProperty
from datetime import datetime

from pyforge.model import Artifact, VersionedArtifact, Snapshot, Message, project_orm_session, Project
from pyforge.model import File

class Globals(MappedClass):

    class __mongometa__:
        name = 'globals'
        session = project_orm_session

    type_s = 'Globals'
    _id = FieldProperty(schema.ObjectId)
    app_config_id = ForeignIdProperty('AppConfig', if_missing=lambda:c.app.config._id)
    last_ticket_num = FieldProperty(int)
    status_names = FieldProperty(str)
    custom_fields = FieldProperty(str)

class TicketHistory(Snapshot):

    class __mongometa__:
        name = 'ticket_history'

    def original(self):
        return Ticket.query.get(_id=self.artifact_id)

    def shorthand_id(self):
        return '%s#%s' % (self.original().shorthand_id(), self.version)

    def url(self):
        return self.original().url() + '?version=%d' % self.version

    def index(self):
        result = Snapshot.index(self)
        result.update(
            title_s='Version %d of %s' % (
                self.version,self.original().title),
            type_s='Ticket Snapshot',
            text=self.data.summary)
        return result

class Ticket(VersionedArtifact):

    class __mongometa__:
        name = 'ticket'
        history_class = TicketHistory

    type_s = 'Ticket'
    _id = FieldProperty(schema.ObjectId)
    version = FieldProperty(0)
    created_date = FieldProperty(datetime, if_missing=datetime.utcnow)

    parent_id = FieldProperty(schema.ObjectId, if_missing=None)
    ticket_num = FieldProperty(int)
    summary = FieldProperty(str)
    description = FieldProperty(str, if_missing='')
    reported_by = FieldProperty(str)
    assigned_to = FieldProperty(str, if_missing='')
    milestone = FieldProperty(str, if_missing='')
    status = FieldProperty(str, if_missing='')
    custom_fields = FieldProperty({str:None})

    comments = RelationProperty('Comment')

    def url(self):
        return c.app.url + '/' + str(self.ticket_num) + '/'

    def shorthand_id(self):
        return '#' + str(self.ticket_num)

    def index(self):
        result = VersionedArtifact.index(self)
        result.update(
            title_s='Ticket %s' % self.ticket_num,
            version_i=self.version,
            type_s=self.type_s,
            text=self.summary)
        return result

    @property
    def attachments(self):
        return Attachment.by_metadata(ticket_id=self._id)

    def root_comments(self):
        if '_id' in self:
            return Comment.query.find(dict(ticket_id=self._id, reply_to=None))
        else:
            return []

    def reply(self):
        while True:
            try:
                c = Comment(ticket_id=self._id)
                return c
            except OperationFailure:
                sleep(0.1)
                continue

class Comment(Message):

    class __mongometa__:
        name = 'ticket_comment'

    type_s = 'Ticket Comment'
    _id = FieldProperty(schema.ObjectId)
    version = FieldProperty(0)
    created_date = FieldProperty(datetime, if_missing=datetime.utcnow)

    author = FieldProperty(str, if_missing='')
    ticket_id = ForeignIdProperty(Ticket)
    kind = FieldProperty(str, if_missing='comment')
    reply_to_id = FieldProperty(schema.ObjectId, if_missing=None)
    text = FieldProperty(str)

    ticket = RelationProperty('Ticket')

    def index(self):
        result = Message.index(self)
        author = self.author()
        result.update(
            title_s='Comment on %s by %s' % (
                self.ticket.shorthand_id(),
                author.display_name
            ),
            type_s=self.type_s
        )
        return result

    @property
    def posted_ago(self):
        comment_td = (datetime.utcnow() - self.timestamp)
        if comment_td.seconds < 3600 and comment_td.days < 1:
            return "%s minutes ago" % (comment_td.seconds / 60)
        elif comment_td.seconds >= 3600 and comment_td.days < 1:
            return "%s hours ago" % (comment_td.seconds / 3600)
        elif comment_td.days >= 1 and comment_td.days < 7:
            return "%s days ago" % comment_td.days
        elif comment_td.days >= 7 and comment_td.days < 30:
            return "%s weeks ago" % (comment_td.days / 7)
        elif comment_td.days >= 30 and comment_td.days < 365:
            return "%s months ago" % (comment_td.days / 30)
        else:
            return "%s years ago" % (comment_td.days / 365)

    def url(self):
        return self.ticket.url() + '#comment-' + str(self._id)

    def shorthand_id(self):
        return '%s-%s' % (self.ticket.shorthand_id, self._id)

class Attachment(File):
    class __mongometa__:
        name = 'attachment.files'
        indexes = [
            'metadata.filename',
            'metadata.ticket_id' ]

    # Override the metadata schema here
    metadata=FieldProperty(dict(
            ticket_id=schema.ObjectId,
            app_config_id=schema.ObjectId,
            filename=str))

    @property
    def ticket(self):
        return Ticket.query.get(_id=self.metadata.ticket_id)

    def url(self):
        return self.ticket.url() + 'attachment/' + self.filename

MappedClass.compile_all()
