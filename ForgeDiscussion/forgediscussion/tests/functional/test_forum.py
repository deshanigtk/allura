import os
import random
import pyforge
import Image
from StringIO import StringIO

import mock
from tg import config
from pylons import g, c

from ming.orm.ormsession import ThreadLocalORMSession

from forgediscussion.tests import TestController
from pyforge import model as M
from pyforge.command import reactor
from pyforge.lib import helpers as h

from forgediscussion import model as FM

class TestForumReactors(TestController):

    def setUp(self):
        TestController.setUp(self)
        self.app.get('/discussion/')
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.shortname':'test',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get('/admin/discussion/')
        assert 'error' not in r
        assert 'Test Forum' in r
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.shortname':'test1',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum 1',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get('/admin/discussion/')
        assert 'error' not in r
        assert 'Test Forum 1' in r
        conf_dir = getattr(config, 'here', os.getcwd())
        test_config = os.environ.get('SANDBOX') and 'sandbox-test.ini' or 'test.ini'
        test_file = os.path.join(conf_dir, test_config)
        cmd = reactor.ReactorCommand('reactor')
        cmd.args = [ test_config ]
        cmd.options = mock.Mock()
        cmd.options.dry_run = True
        cmd.options.proc = 1
        configs = cmd.command()
        self.cmd = cmd
        h.set_context('test', 'discussion')
        self.user_id = M.User.query.get(username='root')._id

    def test_has_access(self):
        assert False == c.app.has_access(M.User.anonymous(), 'test')
        assert True == c.app.has_access(M.User.query.get(username='root'), 'test')

    def test_post(self):
        self._post('discussion.msg.test', 'Test Thread', 'Nothing here')

    def test_bad_post(self):
        self._post('Forumtest', 'Test Thread', 'Nothing here')

    # def test_notify(self):
    #     self._post('discussion.msg.test', 'Test Thread', 'Nothing here',
    #                message_id='test_notify@sf.net')
    #     self._post('discussion.msg.test', 'Test Reply', 'Nothing here, either',
    #                message_id='test_notify1@sf.net',
    #                in_reply_to=[ 'test_notify@sf.net' ])
    #     self._notify('test_notify@sf.net')
    #     self._notify('test_notify1@sf.net')

    def test_reply(self):
        self._post('discussion.msg.test', 'Test Thread', 'Nothing here',
                   message_id='test_reply@sf.net')
        self._post('discussion.msg.test', 'Test Reply', 'Nothing here, either',
                   message_id='test_reply1@sf.net',
                   in_reply_to=[ 'test_reply@sf.net' ])
        assert FM.ForumThread.query.find().count() == 1
        assert FM.ForumPost.query.find().count() == 2

    def test_attach(self):
        self._post('discussion.msg.test', 'Attachment Thread', 'This is a text file',
                   message_id='test.attach.100@sf.net',
                   filename='test.txt',
                   content_type='text/plain')
        self._post('discussion.msg.test', 'Test Thread', 'Nothing here',
                   message_id='test.attach.100@sf.net')
        self._post('discussion.msg.test', 'Attachment Thread', 'This is a text file',
                   message_id='test.attach.100@sf.net',
                   content_type='text/plain')

    def test_threads(self):
        self._post('discussion.msg.test', 'Test', 'test')
        thd = FM.ForumThread.query.find().first()
        url = str('/discussion/test/thread/%s/' % thd._id)
        r = self.app.get(url)
        # Test moderate
        r = self.app.post(url + 'moderate',
                          params={'forum':'test1'})
        assert 'test1' in r.location
        r = self.app.post(url + 'moderate',
                          params={'forum':'test1', 'delete':'on'})
        r = self.app.get(r.location)
        assert len(r.html.findAll('tr')) == 1

    def test_posts(self):
        self._post('discussion.msg.test', 'Test', 'test')
        thd = FM.ForumThread.query.find().first()
        thd_url = str('/discussion/test/thread/%s/' % thd._id)
        r = self.app.get(thd_url)
        p = FM.ForumPost.query.find().first()
        url = str('/discussion/test/thread/%s/%s/' % (thd._id, p.slug))
        r = self.app.get(url)
        r = self.app.post(url, params=dict(subject='New Subject', text='Asdf'))
        assert 'Asdf' in self.app.get(url)
        r = self.app.get(url, params=dict(version=1))
        r = self.app.post(url + 'reply',
                          params=dict(subject='Reply', text='text'))
        self._post('discussion.msg.test', 'Test Reply', 'Nothing here, either',
                   message_id='test_posts@sf.net',
                   in_reply_to=[ p._id ])
        reply = FM.ForumPost.query.find().all()[-1]
        r = self.app.get(thd_url + reply.slug + '/')
        # Check attachments
        r = self.app.post(url + 'attach',
                          upload_files=[('file_info', 'test.txt', 'This is a textfile')])
        r = self.app.post(url + 'attach',
                          upload_files=[('file_info', 'test.asdfasdtxt',
                                         'This is a textfile')])
        r = self.app.get(url)
        for link in r.html.findAll('a'):
            if 'attachment' in link.get('href', ''):
                self.app.get(str(link['href']))
                self.app.post(str(link['href']), params=dict(delete='on'))
        # Moderate
        r = self.app.post(url + 'moderate',
                          params=dict(subject='New Thread', delete='', promote='on'))
        # Find new location
        r = self.app.get(url)
        link = [ a for a in r.html.findAll('a')
                 if a.renderContents() == 'here' ]
        url, slug = str(link[0]['href']).split('#')
        slug = slug.split('-')[-1]
        reply_slug = slug + str(reply.slug[4:])
        r = self.app.post(url + reply_slug + '/moderate',
                          params=dict(subject='', delete='on'))
        r = self.app.post(url + slug + '/moderate',
                          params=dict(subject='', delete='on'))

    def _post(self, topic, subject, body, **kw):
        callback = self.cmd.route_audit(topic, c.app.message_auditor)
        msg = mock.Mock()
        msg.ack = lambda:None
        msg.delivery_info = dict(routing_key=topic)
        message_id = kw.pop('message_id', '%s@test.com' % random.random())
        msg.data = dict(kw,
                        project_id=c.project._id,
                        mount_point='discussion',
                        headers=dict(Subject=subject),
                        user_id=self.user_id,
                        payload=body,
                        message_id=[message_id])
        callback(msg.data, msg)

    def _notify(self, post_id, **kw):
        callback = self.cmd.route_react('discussion.new_post', c.app.notify_subscribers)
        msg = mock.Mock()
        msg.ack = lambda:None
        msg.delivery_info = dict(routing_key='discussion.new_post')
        msg.data = dict(kw,
                        project_id=c.project._id,
                        mount_point='discussion',
                        post_id=post_id)
        callback(msg.data, msg)

class TestForum(TestController):

    def setUp(self):
        TestController.setUp(self)
        self.app.get('/discussion/')
        r = self.app.get('/admin/discussion/')
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.shortname':'TestForum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get('/admin/discussion/')
        assert 'error' not in r
        assert 'TestForum' in r
        h.set_context('test', 'discussion')
        frm = FM.Forum.query.get(shortname='TestForum')
        r = self.app.get('/admin/discussion/')
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.shortname':'ChildForum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Child Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':str(frm._id),
                                  })
        r = self.app.get('/admin/discussion/')
        assert 'error' not in r
        assert 'ChildForum' in r

    def test_forum_search(self):
        r = self.app.get('/discussion/search')
        r = self.app.get('/discussion/search', params=dict(q='foo'))
    
    def test_forum_subscribe(self):
        r = self.app.get('/discussion/subscribe', params={
                'forum-0.shortname':'TestForum',
                'forum-0.subscribed':'on',
                })
        r = self.app.get('/discussion/subscribe', params={
                'forum-0.shortname':'TestForum',
                'forum-0.subscribed':'',
                })
    
    def test_forum_index(self):
        r = self.app.get('/discussion/TestForum/')
        r = self.app.get('/discussion/TestForum/ChildForum/')
    
    def test_posting(self):
        r = self.app.get('/discussion/TestForum/post', params=dict(
                subject='Test Thread',
                text='This is a *test thread*'))
        r = self.app.get('/admin/discussion/')
        assert 'Message posted' in r
        r = self.app.get('/discussion/TestForum/moderate/')

    def test_thread(self):
        thread = self.app.get('/discussion/TestForum/post', params=dict(
                subject='AAA',
                text='aaa')).follow()
        url = thread.request.url
        rep_url = thread.html.find('div',{'class':'reply_post_form push-3 span-16 last clear'}).find('form').get('action')
        thread = self.app.post(str(rep_url), params=dict(
                subject='BBB',
                text='bbb'))
        thread = self.app.get(url)
        # beautiful soup is getting some unicode error here - test without it
        assert '<div class="content clear"><p>aaa</p></div>' in thread.response.body
        assert '<div class="content clear"><p>bbb</p></div>' in thread.response.body
        assert thread.response.body.count('<div class="promote_to_thread_form') == 1
        assert thread.response.body.count('<div class="reply_post_form') == 2
        assert thread.response.body.count('<div class="edit_post_form') == 2

    def test_sidebar_menu(self):
        r = self.app.get('/discussion/')
        sidebarmenu = str(r.html.find('ul',{'id':'sidebarmenu'}))
        assert '<a href="." class=" ">Home</a>' in sidebarmenu
        assert '<a href="/projects/test/admin/discussion" class=" ">Admin</a>' in sidebarmenu
        assert '<a href="search" class=" ">Search</a>' in sidebarmenu
        assert '<a href="/projects/test/discussion/TestForum/" class=" ">Test Forum</a>' in sidebarmenu

class TestForumAdmin(TestController):

    def setUp(self):
        TestController.setUp(self)
        self.app.get('/discussion/')

    def test_forum_CRUD(self):
        r = self.app.get('/admin/discussion/')
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.shortname':'TestForum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get('/admin/discussion/')
        assert 'error' not in r
        assert 'TestForum' in r
        h.set_context('test', 'Forum')
        frm = FM.Forum.query.get(shortname='TestForum')
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.create':'',
                                  'forum-0.delete':'',
                                  'forum-0.id':str(frm._id),
                                  'forum-0.name':'New Test Forum',
                                  'forum-0.description':'My desc'})
        r = self.app.get('/admin/discussion/')
        assert 'error' not in r
        assert 'New Test Forum' in r
        assert 'My desc' in r
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.create':'',
                                  'forum-0.delete':'on',
                                  'forum-0.id':str(frm._id),
                                  'forum-0.name':'New Test Forum',
                                  'forum-0.description':'My desc'})
        r = self.app.get('/admin/discussion/')
        assert 'error' not in r
        assert 'New Test Forum' not in r
        assert 'My desc' not in r

    def test_forum_CRUD_hier(self):
        r = self.app.get('/admin/discussion/')
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.shortname':'TestForum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get('/admin/discussion/')
        assert 'error' not in r
        assert 'TestForum' in r
        h.set_context('test', 'discussion')
        frm = FM.Forum.query.get(shortname='TestForum')
        r = self.app.get('/admin/discussion/')
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.shortname':'ChildForum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Child Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':str(frm._id),
                                  })
        r = self.app.get('/admin/discussion/')
        assert 'error' not in r
        assert 'ChildForum' in r
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.create':'',
                                  'forum-0.delete':'on',
                                  'forum-0.id':str(frm._id),
                                  'forum-0.name':'New Test Forum',
                                  'forum-0.description':'My desc'})
        r = self.app.get('/admin/discussion/')
        assert 'error' not in r
        assert 'TestForum' not in r
        assert 'ChildForum' not in r

    def test_bad_forum_names(self):
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.shortname':'Test.Forum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get('/admin/discussion/')
        assert 'error' in r
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.shortname':'Test/Forum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get('/admin/discussion/')
        assert 'error' in r

    def test_forum_icon(self):
        file_name = 'adobe_header.png'
        file_path = os.path.join(pyforge.__path__[0],'public','images',file_name)
        file_data = file(file_path).read()
        upload = ('new_forum.icon', file_name, file_data)

        h.set_context('test', 'discussion')
        r = self.app.get('/admin/discussion/')
        r = self.app.post('/admin/discussion/update_forums',
                          params={'new_forum.shortname':'TestForum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  },
                          upload_files=[upload]),
        r = self.app.get('/discussion/TestForum/icon')
        image = Image.open(StringIO(r.body))
        assert image.size == (48,48)

