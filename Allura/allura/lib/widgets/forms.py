#       Licensed to the Apache Software Foundation (ASF) under one
#       or more contributor license agreements.  See the NOTICE file
#       distributed with this work for additional information
#       regarding copyright ownership.  The ASF licenses this file
#       to you under the Apache License, Version 2.0 (the
#       "License"); you may not use this file except in compliance
#       with the License.  You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#       Unless required by applicable law or agreed to in writing,
#       software distributed under the License is distributed on an
#       "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#       KIND, either express or implied.  See the License for the
#       specific language governing permissions and limitations
#       under the License.

import logging
import warnings
from pylons import app_globals as g
from allura.lib import validators as V
from allura.lib import helpers as h
from allura.lib import plugin
from allura.lib.widgets import form_fields as ffw
from allura.lib import exceptions as forge_exc
from allura import model as M
from datetime import datetime

from formencode import validators as fev
import formencode

import ew as ew_core
import ew.jinja2_ew as ew

from pytz import common_timezones, country_timezones, country_names

log = logging.getLogger(__name__)

socialnetworks=['Facebook','Linkedin','Twitter','Google+']
weekdays=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

class _HTMLExplanation(ew.InputField):
    template=ew.Snippet(
        '''<label class="grid-4">&nbsp;</label>
           <div class="grid-14" style="margin:2px;">{{widget.text}}</div>
        ''',
        'jinja2')

class NeighborhoodProjectShortNameValidator(fev.FancyValidator):
    def _validate_shortname(self, shortname, neighborhood, state):
        if not h.re_project_name.match(shortname):
            raise forge_exc.ProjectShortnameInvalid(
                    'Please use only letters, numbers, and dashes 3-15 characters long.',
                    shortname, state)

    def _validate_allowed(self, shortname, neighborhood, state):
        p = M.Project.query.get(shortname=shortname, neighborhood_id=neighborhood._id)
        if p:
            raise forge_exc.ProjectConflict(
                    'This project name is taken.',
                    shortname, state)

    def to_python(self, value, state=None, check_allowed=True, neighborhood=None):
        """
        Validate a project shortname.

        If check_allowed is False, the shortname will only be checked for
        correctness.  Otherwise, it will be rejected if already in use or
        otherwise disallowed.
        """
        if neighborhood is None:
            neighborhood = M.Neighborhood.query.get(name=state.full_dict['neighborhood'])
        value = h.really_unicode(value or '').encode('utf-8').lower()
        self._validate_shortname(value, neighborhood, state)
        if check_allowed:
            self._validate_allowed(value, neighborhood, state)
        return value

class ForgeForm(ew.SimpleForm):
    antispam = False
    template = 'jinja:allura:templates/widgets/forge_form.html'
    defaults = dict(
        ew.SimpleForm.defaults,
        submit_text='Save',
        style='standard',
        method='post',
        enctype=None,
        target=None)

    def display_label(self, field, label_text=None):
        ctx = super(ForgeForm, self).context_for(field)
        label_text = (
            label_text
            or ctx.get('label')
            or getattr(field, 'label', None)
            or ctx['name'])
        html = '<label for="%s">%s</label>' % (
            ctx['id'], label_text)
        return h.html.literal(html)

    def context_for(self, field):
        ctx = super(ForgeForm, self).context_for(field)
        if self.antispam:
            ctx['rendered_name'] = g.antispam.enc(ctx['name'])
        return ctx

    def display_field(self, field, ignore_errors=False):
        ctx = self.context_for(field)
        display = field.display(**ctx)
        if ctx['errors'] and field.show_errors and not ignore_errors:
            display = "%s<div class='error'>%s</div>" % (display, ctx['errors'])
        return h.html.literal(display)

    def display_field_by_idx(self, idx, ignore_errors=False):
        warnings.warn(
            'ForgeForm.display_field_by_idx is deprecated; use '
            'ForgeForm.display_field() instead', DeprecationWarning)
        field = self.fields[idx]
        ctx = self.context_for(field)
        display = field.display(**ctx)
        if ctx['errors'] and field.show_errors and not ignore_errors:
            display = "%s<div class='error'>%s</div>" % (display, ctx['errors'])
        return display

class PasswordChangeForm(ForgeForm):
    class fields(ew_core.NameList):
        oldpw = ew.PasswordField(
            label='Old Password', validator=fev.UnicodeString(not_empty=True))
        pw = ew.PasswordField(
            label='New Password',
            validator=fev.UnicodeString(not_empty=True, min=6))
        pw2 = ew.PasswordField(
            label='New Password (again)',
            validator=fev.UnicodeString(not_empty=True))

    @ew_core.core.validator
    def to_python(self, value, state):
        d = super(PasswordChangeForm, self).to_python(value, state)
        if d['pw'] != d['pw2']:
            raise formencode.Invalid('Passwords must match', value, state)
        return d

class PersonalDataForm(ForgeForm):
    class fields(ew_core.NameList):
        sex = ew.SingleSelectField(
            label='Gender',
            options=[ew.Option(py_value=v,label=v,selected=False)
                     for v in ['Male', 'Female', 'Unknown', 'Other']],
            validator=formencode.All(
                V.OneOfValidator(['Male', 'Female', 'Unknown', 'Other']),
                fev.UnicodeString(not_empty=True)))
        birthdate = ew.TextField(
            label='Birth date',
            validator=V.DateValidator(),
            attrs=dict(value=None))
        exp = _HTMLExplanation(
            text="Use the format DD/MM/YYYY",
            show_errors=False)
        country = ew.SingleSelectField(
            label='Country of residence',
            validator=V.MapValidator(country_names, not_empty=False),
            options = [
                ew.Option(
                    py_value=" ", label=" -- Unknown -- ", selected=False)] +\
                [ew.Option(py_value=c, label=n, selected=False)
                 for c,n in sorted(country_names.items(),
                                   key=lambda (k,v):v)],
            attrs={'onchange':'selectTimezone(this.value)'})
        city = ew.TextField(
            label='City of residence',
            attrs=dict(value=None),
            validator=fev.UnicodeString(not_empty=False))
        timezone=ew.SingleSelectField(
            label='Timezone',
            attrs={'id':'tz'},
            validator=V.OneOfValidator(common_timezones, not_empty=False),
            options=[
                 ew.Option(
                     py_value=" ",
                     label=" -- Unknown -- ")] + \
                 [ew.Option(py_value=n, label=n)
                  for n in sorted(common_timezones)])

    def display(self, **kw):
        user = kw.get('user')

        for opt in self.fields['sex'].options:
            if opt.label == user.sex:
                opt.selected = True
            else:
                opt.selected = False

        if user.get_pref('birthdate'):
            self.fields['birthdate'].attrs['value'] = \
                user.get_pref('birthdate').strftime('%d/%m/%Y')
        else:
            self.fields['birthdate'].attrs['value'] = ''

        for opt in self.fields['country'].options:
            if opt.label == user.localization.country:
                opt.selected = True
            elif opt.py_value == " " and user.localization.country is None:
                opt.selected = True
            else:
                opt.selected = False

        if user.localization.city:
            self.fields['city'].attrs['value'] = user.localization.city
        else:
            self.fields['city'].attrs['value'] = ''

        for opt in self.fields['timezone'].options:
            if opt.label == user.timezone:
                opt.selected = True
            elif opt.py_value == " " and user.timezone is None:
                opt.selected = True
            else:
                opt.selected = False

        return super(ForgeForm, self).display(**kw)

    def resources(self):
        def _append(x, y):
            return x + y

        yield ew.JSScript('''
var $allTimezones = $("#tz").clone();
var $t = {};
''' + \
    reduce(_append, [
        '$t["'+ el +'"] = ' + str([name.encode('utf-8')
                                  for name in country_timezones[el]]) + ";\n"
        for el in country_timezones]) + '''
function selectTimezone($country){
     if($country == " "){
         $("#tz").replaceWith($allTimezones);
     }
     else{
         $("#tz option:gt(0)").remove();
         $.each($t[$country], function(index, value){
             $("#tz").append($("<option></option>").attr("value", value).text(value))
         })
     }
}''')

class AddTelNumberForm(ForgeForm):
    defaults=dict(ForgeForm.defaults)

    class fields(ew_core.NameList):
        newnumber = ew.TextField(
            label='New telephone number',
            attrs={'value':''},
            validator=fev.UnicodeString(not_empty=True))

    def display(self, **kw):
        initial_value = kw.get('initial_value','')
        self.fields['newnumber'].attrs['value'] = initial_value
        return super(ForgeForm, self).display(**kw)

class AddWebsiteForm(ForgeForm):
    defaults=dict(ForgeForm.defaults)

    class fields(ew_core.NameList):
        newwebsite = ew.TextField(
            label='New website url',
            attrs={'value':''},
            validator=fev.URL())

    def display(self, **kw):
        initial_value = kw.get('initial_value','')
        self.fields['newwebsite'].attrs['value'] = initial_value
        return super(ForgeForm, self).display(**kw)

class SkypeAccountForm(ForgeForm):
    defaults=dict(ForgeForm.defaults)

    class fields(ew_core.NameList):
        skypeaccount = ew.TextField(
            label='Skype account',
            attrs={'value':''},
            validator=fev.UnicodeString(not_empty=False))

    def display(self, **kw):
        initial_value = kw.get('initial_value','')
        self.fields['skypeaccount'].attrs['value'] = initial_value
        return super(ForgeForm, self).display(**kw)

class RemoveTextValueForm(ForgeForm):
    defaults=dict(ForgeForm.defaults, submit_text=None, show_errors=False)

    def display(self, **kw):
        initial_value = kw.get('value','')
        label = kw.get('label','')
        description = kw.get('description')

        self.fields = [
            ew.RowField(
                show_errors=False,
                fields=[
                    ffw.DisplayOnlyField(text=label),
                    ffw.DisplayOnlyField(
                        name='oldvalue',
                        label=initial_value,
                        attrs={'value':initial_value},
                        show_errors=False),
                    ew.SubmitButton(
                        show_label=False,
                        attrs={'value':'Remove'},
                        show_errors=False)])]
        if description:
            self.fields.append(
                _HTMLExplanation(
                    text=description,
                    show_errors=False))
        return super(ForgeForm, self).display(**kw)

    @ew_core.core.validator
    def to_python(self, kw, state):
        d = super(RemoveTextValueForm, self).to_python(kw, state)
        d["oldvalue"] = kw.get('oldvalue', '')
        return d

class AddSocialNetworkForm(ForgeForm):
    defaults=dict(ForgeForm.defaults)

    class fields(ew_core.NameList):
        socialnetwork = ew.SingleSelectField(
            label='Social network',
            options=[ew.Option(py_value=name, label=name)
                     for name in socialnetworks],
            validator=formencode.All(
                V.OneOfValidator(socialnetworks),
                fev.UnicodeString(not_empty=True)))
        accounturl = ew.TextField(
            label='Account url',
            validator=fev.UnicodeString(not_empty=True))

class RemoveSocialNetworkForm(ForgeForm):
    defaults=dict(ForgeForm.defaults, submit_text=None, show_errors=False)

    def display(self, **kw):
        account = kw.get('account','')
        socialnetwork = kw.get('socialnetwork','')

        self.fields = [
            ew.RowField(
                show_errors=False,
                fields=[
                    ffw.DisplayOnlyField(
                        text='%s account' % socialnetwork,
                        name="socialnetwork",
                        attrs={'value':socialnetwork},
                        show_errors=False),
                    ffw.DisplayOnlyField(
                        name="account",
                        attrs={'value':account},
                        show_errors=False),
                    ew.SubmitButton(
                        show_label=False,
                        attrs={'value':'Remove'},
                        show_errors=False)])]
        return super(ForgeForm, self).display(**kw)

    @ew_core.core.validator
    def to_python(self, kw, state):
        d = super(RemoveSocialNetworkForm, self).to_python(kw, state)
        d["account"] = kw.get('account', '')
        d["socialnetwork"] = kw.get('socialnetwork', '')
        return d

class AddInactivePeriodForm(ForgeForm):
    class fields(ew_core.NameList):
        startdate = ew.TextField(
            label='Start date',
            validator=formencode.All(
                V.DateValidator(),
                fev.UnicodeString(not_empty=True)))
        enddate = ew.TextField(
            label='End date',
            validator=formencode.All(
                V.DateValidator(),
                fev.UnicodeString(not_empty=True)))

    @ew_core.core.validator
    def to_python(self, kw, state):
        d = super(AddInactivePeriodForm, self).to_python(kw, state)
        if d['startdate'] > d['enddate']:
                raise formencode.Invalid(
                   'Invalid period: start date greater than end date.',
                    kw, state)
        return d

class RemoveInactivePeriodForm(ForgeForm):
    defaults=dict(ForgeForm.defaults, submit_text=None, show_errors=False)

    def display(self, **kw):
        startdate = kw.get('startdate')
        enddate = kw.get('enddate')

        self.fields = [
            ew.RowField(
                show_label=False,
                show_errors=False,
                fields=[
                    ffw.DisplayOnlyField(
                        name='startdate',
                        attrs={'value':startdate.strftime('%d/%m/%Y')},
                        show_errors=False),
                    ffw.DisplayOnlyField(
                        name='enddate',
                        attrs={'value':enddate.strftime('%d/%m/%Y')},
                        show_errors=False),
                    ew.SubmitButton(
                        attrs={'value':'Remove'},
                        show_errors=False)])]
        return super(ForgeForm, self).display(**kw)

    @ew_core.core.validator
    def to_python(self, kw, state):
        d = super(RemoveInactivePeriodForm, self).to_python(kw, state)
        d['startdate'] = V.convertDate(kw.get('startdate',''))
        d['enddate'] = V.convertDate(kw.get('enddate',''))
        return d

class AddTimeSlotForm(ForgeForm):
    class fields(ew_core.NameList):
        weekday = ew.SingleSelectField(
            label='Weekday',
            options=[ew.Option(py_value=wd, label=wd)
                     for wd in weekdays],
            validator=formencode.All(
                V.OneOfValidator(weekdays),
                fev.UnicodeString(not_empty=True)))
        starttime = ew.TextField(
            label='Start time',
            validator=formencode.All(
                V.TimeValidator(),
                fev.UnicodeString(not_empty=True)))
        endtime = ew.TextField(
            label='End time',
            validator=formencode.All(
                V.TimeValidator(),
                fev.UnicodeString(not_empty=True)))

    @ew_core.core.validator
    def to_python(self, kw, state):
        d = super(AddTimeSlotForm, self).to_python(kw, state)
        if (d['starttime']['h'], d['starttime']['m']) > \
           (d['endtime']['h'], d['endtime']['m']):
                raise formencode.Invalid(
                   'Invalid period: start time greater than end time.',
                    kw, state)
        return d

class RemoveTimeSlotForm(ForgeForm):
    defaults=dict(ForgeForm.defaults, submit_text=None, show_errors=False)

    def display(self, **kw):
        weekday = kw.get('weekday','')
        starttime = kw.get('starttime')
        endtime = kw.get('endtime')

        self.fields = [
            ew.RowField(
                show_errors=False,
                show_label=False,
                fields=[
                    ffw.DisplayOnlyField(
                        name='weekday',
                        attrs={'value':weekday},
                        show_errors=False),
                    ffw.DisplayOnlyField(
                        name='starttime',
                        attrs={'value':starttime.strftime('%H:%M')},
                        show_errors=False),
                    ffw.DisplayOnlyField(
                        name='endtime',
                        attrs={'value':endtime.strftime('%H:%M')},
                        show_errors=False),
                    ew.SubmitButton(
                        show_errors=False,
                        attrs={'value':'Remove'})])]
        return super(ForgeForm, self).display(**kw)

    @ew_core.core.validator
    def to_python(self, kw, state):
        d = super(RemoveTimeSlotForm, self).to_python(kw, state)
        d["weekday"] = kw.get('weekday', None)
        d['starttime'] = V.convertTime(kw.get('starttime',''))
        d['endtime'] = V.convertTime(kw.get('endtime',''))
        return d


class RemoveTroveCategoryForm(ForgeForm):
    defaults=dict(ForgeForm.defaults, submit_text=None, show_errors=False)

    def display(self, **kw):
        cat = kw.get('category')

        self.fields = [
            ew.RowField(
                show_errors=False,
                show_label=False,
                fields=[
                    ew.LinkField(
                        text=cat.fullname,
                        href="/categories/%s" % cat.shortname),
                    ew.SubmitButton(
                        show_errors=False,
                        attrs={'value':'Remove'})],
                hidden_fields=[
                    ew.HiddenField(
                        name='categoryid',
                        attrs={'value':cat.trove_cat_id})])]
        return super(ForgeForm, self).display(**kw)

    @ew_core.core.validator
    def to_python(self, kw, state):
        d = super(RemoveTroveCategoryForm, self).to_python(kw, state)
        d["categoryid"] = kw.get('categoryid')
        if d["categoryid"]:
            d["categoryid"] = int(d['categoryid'])
        return d

class AddTroveCategoryForm(ForgeForm):
    defaults=dict(ForgeForm.defaults)

    class fields(ew_core.NameList):
        uppercategory_id = ew.HiddenField(
            attrs={'value':''},
            show_errors=False)
        categoryname = ew.TextField(
            label="Category name",
            validator=fev.UnicodeString(not_empty=True))

    def display(self, **kw):
        upper_category = kw.get('uppercategory_id',0)

        self.fields['uppercategory_id'].attrs['value'] = upper_category
        return super(ForgeForm, self).display(**kw)

    @ew_core.core.validator
    def to_python(self, kw, state):
        d = super(AddTroveCategoryForm, self).to_python(kw, state)
        d["uppercategory_id"] = kw.get('uppercategory_id', 0)
        return d

class AddUserSkillForm(ForgeForm):
    defaults=dict(ForgeForm.defaults)

    class fields(ew_core.NameList):
        selected_skill=ew.HiddenField(
            attrs={'value':''},
            show_errors=False,
            validator=fev.UnicodeString(not_empty=True))
        level=ew.SingleSelectField(
            label="Level of knowledge",
            options=[
                ew.Option(py_value="low",label="Low level"),
                ew.Option(py_value="medium",label="Medium level"),
                ew.Option(py_value="high",label="Advanced level")],
            validator=formencode.All(
                V.OneOfValidator(['low','medium','high']),
                fev.UnicodeString(not_empty=True)))
        comment=ew.TextArea(
            label="Additional comments",
            validator=fev.UnicodeString(not_empty=False),
            attrs={'rows':5,'cols':30})

    def display(self, **kw):
        category = kw.get('selected_skill')

        self.fields["selected_skill"].attrs['value']=category
        return super(ForgeForm, self).display(**kw)

class SelectSubCategoryForm(ForgeForm):
    defaults=dict(ForgeForm.defaults, submit_text="Continue")

    class fields(ew_core.NameList):
        selected_category=ew.SingleSelectField(
            name="selected_category",
            label="Available categories",
            options=[])

    def display(self, **kw):
        categories = kw.get('categories')

        self.fields['selected_category'].options= \
            [ew.Option(py_value=el.trove_cat_id,label=el.fullname)
             for el in categories]
        self.fields['selected_category'].validator= \
            validator=formencode.All(
                V.OneOfValidator(categories),
                fev.UnicodeString(not_empty=True))
        return super(ForgeForm, self).display(**kw)

class RemoveSkillForm(ForgeForm):
    defaults=dict(ForgeForm.defaults, submit_text=None, show_errors=False)

    def display(self, **kw):
        skill = kw.get('skill')
        comment = skill['comment']
        if not comment:
            comment = "&nbsp;"

        self.fields = [
            ew.RowField(
                show_errors=False,
                hidden_fields=[
                    ew.HiddenField(
                        name="categoryid",
                        attrs={'value':skill['skill'].trove_cat_id},
                        show_errors=False)
                ],
                fields=[
                    ffw.DisplayOnlyField(text=skill['skill'].fullpath),
                    ffw.DisplayOnlyField(text=skill['level']),
                    ffw.DisplayOnlyField(text=comment),
                    ew.SubmitButton(
                        show_label=False,
                        attrs={'value':'Remove'},
                        show_errors=False)])]
        return super(ForgeForm, self).display(**kw)

    @ew_core.core.validator
    def to_python(self, kw, state):
        d = super(RemoveSkillForm, self).to_python(kw, state)
        d["categoryid"] = kw.get('categoryid', None)
        return d

class UploadKeyForm(ForgeForm):
    class fields(ew_core.NameList):
        key = ew.TextArea(label='SSH Public Key')

class RegistrationForm(ForgeForm):
    class fields(ew_core.NameList):
        display_name = ew.TextField(
            label='Displayed Name',
            validator=fev.UnicodeString(not_empty=True))
        username = ew.TextField(
            label='Desired Username',
            validator=fev.Regex(
                h.re_project_name))
        username.validator._messages['invalid'] = (
            'Usernames must include only letters, numbers, and dashes.'
            ' They must also start with a letter and be at least 3 characters'
            ' long.')
        pw = ew.PasswordField(
            label='New Password',
            validator=fev.UnicodeString(not_empty=True, min=8))
        pw2 = ew.PasswordField(
            label='New Password (again)',
            validator=fev.UnicodeString(not_empty=True))

    @ew_core.core.validator
    def to_python(self, value, state):
        d = super(RegistrationForm, self).to_python(value, state)
        value['username'] = username = value['username'].lower()
        if M.User.by_username(username):
            raise formencode.Invalid('That username is already taken. Please choose another.',
                                    value, state)
        if d['pw'] != d['pw2']:
            raise formencode.Invalid('Passwords must match', value, state)
        return d

class AdminForm(ForgeForm):
    template = 'jinja:allura:templates/widgets/admin_form.html'

class NeighborhoodOverviewForm(ForgeForm):
    template = 'jinja:allura:templates/widgets/neighborhood_overview_form.html'

    class fields(ew_core.NameList):
        name = ew.TextField()
        redirect = ew.TextField()
        homepage = ffw.AutoResizeTextarea()
        allow_browse = ew.Checkbox(label='')
        show_title = ew.Checkbox(label='')
        css = ffw.AutoResizeTextarea()
        project_template = ffw.AutoResizeTextarea(
                validator=V.JsonValidator(if_empty=''))
        icon = ew.FileField()
        tracking_id = ew.TextField()
        project_list_url = ew.TextField(validator=fev.URL())
        anchored_tools = ffw.AutoResizeTextarea()

    def from_python(self, value, state):
        if value.features['css'] == "picker":
            self.list_color_inputs = True
            self.color_inputs = value.get_css_for_picker()
        else:
            self.list_color_inputs = False
            self.color_inputs = []
        return super(NeighborhoodOverviewForm, self).from_python(value, state)

    def display_field(self, field, ignore_errors=False):
        if field.name == "css" and self.list_color_inputs:
            display = '<table class="table_class">'
            ctx = self.context_for(field)
            for inp in self.color_inputs:
                additional_inputs = inp.get('additional', '')
                empty_val = False
                if inp['value'] is None or inp['value'] == '':
                    empty_val = True
                display += '<tr><td class="left"><label>%(label)s</label></td>'\
                           '<td><input type="checkbox" name="%(ctx_name)s-%(inp_name)s-def" %(def_checked)s>default</td>'\
                           '<td class="right"><div class="%(ctx_name)s-%(inp_name)s-inp"><table class="input_inner">'\
                           '<tr><td><input type="text" class="%(inp_type)s" name="%(ctx_name)s-%(inp_name)s" '\
                           'value="%(inp_value)s"></td><td>%(inp_additional)s</td></tr></table></div></td></tr>\n' % {'ctx_id': ctx['id'],
                                                            'ctx_name': ctx['name'],
                                                            'inp_name': inp['name'],
                                                            'inp_value': inp['value'],
                                                            'label': inp['label'],
                                                            'inp_type': inp['type'],
                                                            'def_checked': 'checked="checked"' if empty_val else '',
                                                            'inp_additional': additional_inputs}
            display += '</table>'

            if ctx['errors'] and field.show_errors and not ignore_errors:
                display = "%s<div class='error'>%s</div>" % (display, ctx['errors'])

            return h.html.literal(display)
        else:
            return super(NeighborhoodOverviewForm, self).display_field(field, ignore_errors)

    @ew_core.core.validator
    def to_python(self, value, state):
        d = super(NeighborhoodOverviewForm, self).to_python(value, state)
        neighborhood = M.Neighborhood.query.get(name=d.get('name', None))
        if neighborhood and neighborhood.features['css'] == "picker":
            css_form_dict = {}
            for key in value.keys():
                def_key = "%s-def" % (key)
                if key[:4] == "css-" and def_key not in value:
                    css_form_dict[key[4:]] = value[key]
            d['css'] = M.Neighborhood.compile_css_for_picker(css_form_dict)
        return d

    def resources(self):
        for r in super(NeighborhoodOverviewForm, self).resources(): yield r
        yield ew.CSSLink('css/colorPicker.css')
        yield ew.CSSLink('css/jqfontselector.css')
        yield ew.CSSScript('''
table.table_class, table.input_inner{
  margin: 0;
  padding: 0;
  width: 99%;
}

table.table_class .left{ text-align: left; }
table.table_class .right{ text-align: right; width: 50%;}
table.table_class tbody tr td { border: none; }
table.table_class select.add_opt {width: 5em; margin:0; padding: 0;}
        ''')
        yield ew.JSLink('js/jquery.colorPicker.js')
        yield ew.JSLink('js/jqfontselector.js')
        yield ew.JSScript('''
            $(function(){
              $('.table_class').find('input[type="checkbox"]').each(function(index, element) {
                var cb_name = $(this).attr('name');
                var inp_name = cb_name.substr(0, cb_name.length-4);
                var inp_el = $('div[class="'+inp_name+'-inp"]');

                if ($(this).attr('checked')) {
                  inp_el.hide();
                }

                $(element).click(function(e) {
                  if ($(this).attr('checked')) {
                    inp_el.hide();
                  } else {
                    inp_el.show();
                  }
                });
              });

              $('.table_class').find('input.color').each(function(index, element) {
                $(element).colorPicker();
              });
              $('.table_class').find('input.font').each(function(index, element) {
                $(element).fontSelector();
              });
            });
        ''')

class NeighborhoodAddProjectForm(ForgeForm):
    template = 'jinja:allura:templates/widgets/neighborhood_add_project.html'
    antispam = True
    defaults = dict(
        ForgeForm.defaults,
        method='post',
        submit_text='Start',
        neighborhood=None)

    class fields(ew_core.NameList):
        project_description = ew.HiddenField(label='Public Description')
        neighborhood = ew.HiddenField(label='Neighborhood')
        private_project = ew.Checkbox(label="", attrs={'class':'unlabeled'})
        project_name = ew.InputField(label='Project Name', field_type='text',
            validator=formencode.All(
                fev.UnicodeString(not_empty=True, max=40),
                V.MaxBytesValidator(max=40)))
        project_unixname = ew.InputField(
            label='Short Name', field_type='text',
            validator=None)  # will be set in __init__
        tools = ew.CheckboxSet(name='tools', options=[
            ## Required for Neighborhood functional tests to pass
            ew.Option(label='Wiki', html_value='wiki', selected=True)
        ])

    def __init__(self, *args, **kwargs):
        super(NeighborhoodAddProjectForm, self).__init__(*args, **kwargs)
        # get the shortname validator from the provider
        provider = plugin.ProjectRegistrationProvider.get()
        self.fields.project_unixname.validator = provider.shortname_validator
        ## Dynamically generating CheckboxSet of installable tools
        from allura.lib.widgets import forms
        self.fields.tools.options = [
                forms.ew.Option(label=tool.tool_label, html_value=ep)
                    for ep,tool in g.entry_points["tool"].iteritems()
                    if tool.installable and tool.status == 'production'
            ]

    def resources(self):
        for r in super(NeighborhoodAddProjectForm, self).resources(): yield r
        yield ew.CSSLink('css/add_project.css')
        neighborhood = g.antispam.enc('neighborhood')
        project_name = g.antispam.enc('project_name')
        project_unixname = g.antispam.enc('project_unixname')

        yield ew.JSScript('''
            $(function(){
                var $scms = $('input[type=checkbox].scm');
                var $nbhd_input = $('input[name="%(neighborhood)s"]');
                var $name_input = $('input[name="%(project_name)s"]');
                var $unixname_input = $('input[name="%(project_unixname)s"]');
                var $url_fragment = $('#url_fragment');
                var $form = $name_input.closest('form');
                var delay = (function(){
                  var timers = {};
                  return function(callback, ms){
                    clearTimeout (timers[callback]);
                    timers[callback] = setTimeout(callback, ms);
                  };
                })();
                $name_input.focus();
                var update_icon = function($input) {
                    var $success_icon = $input.parent().next().find('.success_icon');
                    var $error_icon = $input.parent().next().find('.error_icon');
                    var is_error = $input.nextAll('.error').is(':visible');
                    $success_icon.toggle(!is_error);
                    $error_icon.toggle(is_error);
                };
                if ($name_input.val() !== '') {
                    update_icon($name_input);
                }
                if ($unixname_input.val() !== '') {
                    update_icon($unixname_input);
                }
                var handle_error = function($input, message) {
                    var $error_field = $input.nextAll('.error');
                    if ($error_field.length === 0) {
                        $error_field = $('<div class="error" style="display: none"></div>').insertAfter($input);
                    }
                    $error_field.text(message).toggle(!!message);
                    update_icon($input);
                };
                $form.submit(function(e) {
                    var has_errors = $name_input.add($unixname_input).nextAll('.error').is(':visible');
                    if (has_errors || $name_input.val() === '' || $unixname_input.val() === '') {
                        e.preventDefault();
                        alert('You must resolve the issues with the project name.');
                        return false;
                    }
                });
                $scms.change(function(){
                    if ( $(this).attr('checked') ) {
                        var on = this;
                        $scms.each(function(){
                            if ( this !== on ) {
                                $(this).removeAttr('checked');
                            }
                        });
                    }
                });
                var check_names = function() {
                    var data = {
                        'neighborhood': $nbhd_input.val(),
                        'project_name': $name_input.val(),
                        'project_unixname': $unixname_input.val()
                    };
                    $.getJSON('check_names', data, function(result){
                        handle_error($name_input, result.project_name);
                        handle_error($unixname_input, result.project_unixname);
                    });
                };
                var manual = false;
                $name_input.keyup(function(){
                    delay(function() {
                        if (!manual) {
                            var data = {
                                'project_name':$name_input.val()
                            };
                            $.getJSON('suggest_name', data, function(result){
                                $unixname_input.val(result.suggested_name);
                                $url_fragment.html(result.suggested_name);
                                check_names();
                            });
                        } else {
                            check_names();
                        }
                    }, 500);
                });
                $unixname_input.change(function() {
                    manual = true;
                });
                $unixname_input.keyup(function(){
                    $url_fragment.html($unixname_input.val());
                    delay(check_names, 500);
                });
            });
        ''' % dict(neighborhood=neighborhood, project_name=project_name, project_unixname=project_unixname))


class MoveTicketForm(ForgeForm):
    defaults = dict(
        ForgeForm.defaults,
        action='',
        method='post',
        submit_text='Move')

    class fields(ew_core.NameList):
        tracker = ew.SingleSelectField(
            label='Tracker mount point',
            options = [])

    def __init__(self, *args, **kwargs):
        trackers = kwargs.pop('trackers', [])
        super(MoveTicketForm, self).__init__(*args, **kwargs)
        self.fields.tracker.options = (
            [ew.Option(py_value=v, label=l, selected=s)
             for v, l, s in sorted(trackers, key=lambda x: x[1])])
