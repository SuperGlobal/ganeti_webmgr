import json

from django import forms
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect, \
    HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext


from object_permissions import get_model_perms, grant, revoke, get_user_perms
from object_permissions.models import UserGroup
from object_permissions.views.permissions import ObjectPermissionForm


def detail(request, id):
    """
    Display user_group details
    """
    #TODO permission check
    group = get_object_or_404(UserGroup, id=id)
    return render_to_response("user_groups/detail.html", {'group':group}, \
                              context_instance=RequestContext(request))


class UserGroupForm(forms.Form):
    user_group = None

    def __init__(self, user_group=None, *args, **kwargs):
        self.user_group=user_group
        super(UserGroupForm, self).__init__(*args, **kwargs)


class UserForm(UserGroupForm):
    """
    Base form for dealing with users
    """
    user = forms.ModelChoiceField(queryset=User.objects.all())


class AddUserForm(UserForm):
    def clean_user(self):
        """ Validate that user is not in user_group already """
        user = self.cleaned_data['user']
        if self.user_group.users.filter(id=user.id).exists():
            raise forms.ValidationError("User is already a member of this group")
        return user


class RemoveUserForm(UserForm):
    def clean_user(self):
        """ Validate that user is in user_group """
        user = self.cleaned_data['user']
        if not self.user_group.users.filter(id=user.id).exists():
            raise forms.ValidationError("User is not a member of this group")
        return user


def add_user(request, id):
    """
    ajax call to add a user to an user_group.
    """
    user = request.user
    user_group = get_object_or_404(UserGroup, id=id)
    
    if not (user.is_superuser or user.has_perm('admin', user_group)):
        return HttpResponseForbidden('You do not have sufficient privileges')
    
    if request.method == 'POST':
        form = AddUserForm(user_group, request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            user_group.users.add(user)
            
            # return html for new user row
            return render_to_response("user_groups/user_row.html", \
                                      {'user':user, 'group':user_group})
        
        # error in form return ajax response
        content = json.dumps(form.errors)
        return HttpResponse(content, mimetype='application/json')

    form = AddUserForm()
    return render_to_response("user_groups/add_user.html",\
                              {'form':form, 'group':user_group}, \
                              context_instance=RequestContext(request))


def remove_user(request, id):
    """
    Ajax call to remove a user from an user_group
    """
    user = request.user
    user_group = get_object_or_404(UserGroup, id=id)
    
    if not (user.is_superuser or user.has_perm('admin', user_group)):
        return HttpResponseForbidden('You do not have sufficient privileges')
    
    if request.method != 'POST':
        return HttpResponseNotAllowed('GET')

    form = RemoveUserForm(user_group, request.POST)
    if form.is_valid():
        user = form.cleaned_data['user']
        user_group.users.remove(user)
        
        # return success
        return HttpResponse('1', mimetype='application/json')
        
    # error in form return ajax response
    content = json.dumps(form.errors)
    return HttpResponse(content, mimetype='application/json')


def user_permissions(request, id, user_id):
    """
    Ajax call to update a user's permissions
    """
    user = request.user
    user_group = get_object_or_404(UserGroup, id=id)
    
    if not (user.is_superuser or user.has_perm('admin', user_group)):
        return HttpResponseForbidden('You do not have sufficient privileges')
    
    model_perms = get_model_perms(user_group)
    choices = zip(model_perms, model_perms)
    
    if request.method == 'POST':
        form = ObjectPermissionForm(user_id, choices, request.POST)
        if form.is_valid():
            perms = form.cleaned_data['permissions']
            user = form.cleaned_data['user']
            # update perms - grant all perms selected in the form.  Revoke all
            # other available perms that were not selected.
            for perm in perms:
                grant(user, perm, user_group)
            for perm in [p for p in model_perms if p not in perms]:
                revoke(user, perm, user_group)
            
            # return html to replace existing user row
            return render_to_response("user_groups/user_row.html", {'user':user})
        
        # error in form return ajax response
        content = json.dumps(form.errors)
        return HttpResponse(content, mimetype='application/json')

    form_user = get_object_or_404(User, id=user_id)
    data = {'permissions':get_user_perms(form_user, user_group)}
    form = ObjectPermissionForm(user_id, choices, data)
    return render_to_response("user_groups/permissions.html", \
                              {'form':form, 'group':user_group}, \
                              context_instance=RequestContext(request))