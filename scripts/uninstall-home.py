import sys
import logging

from pylons import c
from ming.orm import session

from allura.lib import helpers as h
from allura import model as M
from forgewiki import model as WM
from allura.ext.project_home import ProjectHomeApp

log = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
log.addHandler(handler)

def main():
    test = sys.argv[-1] == 'test'
    all_projects = M.Project.query.find().all()
    log.info('Removing "home" tools')
    for project in all_projects:
        c.project = project
        old_home_app = project.app_instance('home')
        if isinstance(old_home_app, ProjectHomeApp):

            # remove the existing home tool
            if test:
                log.info('would remove "home" tool from project ' + project.shortname)
            else:
                log.info('removing "home" tool from project ' + project.shortname)
                project.uninstall_app('home')

            # ...and put a Wiki in its place (note we only create a Wiki if we deleted the old home)
            if test:
                log.info('would create Wiki "home" for project ' + project.shortname)
            else:
                log.info('creating Wiki "home" for project ' + project.shortname)
                home_title = project.homepage_title or 'Home'
                home_text = project.description or ''
                if home_text == 'You can edit this description in the admin page':
                    home_text = 'You can edit this description'

                # re-number all the mounts so the new Wiki comes first
                mounts = project.ordered_mounts()
                new_home_app = project.install_app('Wiki', 'home', 'Home')
                mounts = [{'ordinal':0, 'ac':new_home_app.config}] + mounts
                for i, mount in enumerate(mounts):
                    if 'ac' in mount:
                        mount['ac'].options['ordinal'] = i
                        session(mount['ac']).flush()
                    elif 'sub' in mount:
                        mount['sub'].ordinal = i
                        session(mount['sub']).flush()

                # make it look as much like the old home tool as possible
                new_home_app.config.options['show_left_bar'] = False
                new_home_app.config.options['show_discussion'] = False

                # now let's fix the home page itself
                log.info('updating home page to "%s"' % home_title)
                new_home_page = WM.Page.query.find(dict(app_config_id=new_home_app.config._id)).first()
                with h.push_config(c, app=new_home_app):
                    if new_home_page is None:
                        # weird: we didn't find the existing home page
                        log.warning('hmmm, actually creating the home page ("%s") for project "%s" from scratch' % (home_title, project.shortname))
                        new_home_page = WM.Page.upsert(home_title)
                        new_home_page.viewable_by = ['all']
                    new_home_page.title = home_title
                    new_home_page.text = home_text
                    new_home_page.commit()
                assert new_home_page is not None
                assert new_home_page.title == home_title
                assert new_home_page.version == 2

                # if we changed the home page name, make sure the Wiki knows that's the root page
                new_home_app.root_page_name = home_title

            session(project).flush()
        session(project).clear()

if __name__ == '__main__':
    main()
