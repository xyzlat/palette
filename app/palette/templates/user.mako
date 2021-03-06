# -*- coding: utf-8 -*-
<%inherit file="webapp.mako" />

<%block name="title">
<title>Palette - User Configuration</title>
</%block>

<div class="content">
  <div>
    <div class="top-zone">
      <div class="refresh">
        <p>
          <span class="message"></span>
          Updated <span id="last-update"></span>
          %if req.remote_user.roleid >= req.remote_user.role.MANAGER_ADMIN:
          <i class="fa fa-fw fa-refresh inactive"></i>
          %endif
        </p>
      </div>
      <h1>Users</h1>
    </div>
    <div class="bottom-zone">
      <div class="letters"></div>
      <div id="user-list">
        <%include file="empty.mako" />
      </div>
    </div> <!-- bottom-zone -->
  </div>
</div> <!-- content -->

<script id="user-list-template" type="x-tmpl-mustache">
  {{#users}}
  <article class="item" data-toggle="item">
    <div class="summary clearfix">
      <i class="fa fa-fw fa-user"></i>
      <div>
        <div class="col2">
          <h3>{{friendly-name}}</h3>
          <p>{{visited-info}}</p>
        </div>
        <div class="col2">
          <div>
            <span class="label">Palette Role</span>
            <span class="display-role">{{palette-display-role}}</span>
          </div>
          <div class="email-level">
            <span class="label">Email Alerts</span>
            <div class="onoffswitch"
                 data-name="{{name}}" data-href="/rest/users/email-level">
              {{email-level}}
            </div>
          </div>
        </div>
      </div>
      <i class="fa fa-fw fa-angle-down expand"></i>
    </div>
    <div class="description clearfix">
      <div>
        <div class="col2">
          <p class="heading">Tableau User Details</span>
          <article>
            <span class="label">User Name</span>{{name}}
          </article>
          <article>
            <span class="label">License Level</span>{{license-info}}
          </article>
          <article>
            <span class="label">Role</span>{{tableau-info}}
          </article>

          <article><span class="label">Email</span>
                <span>{{email}}</span>
          </article>
          <article>
            <span class="label">Created</span>{{system-created-at}}
          </article>
          <article>
            <span class="label">Last Tableau Login</span>{{login-at}}
          </article>
        </div>
        <div class="col2">
%if req.remote_user.roleid == req.remote_user.role.SUPER_ADMIN:
          {{^current}}
          <article class="perms">
            <span class="label">Palette Admin Permissions</span>
            <div>
              <span class="btn-group admin-type"
                    data-userid="{{userid}}" data-href="/rest/users/admin">
                {{roleid}}
              </span>
              <a id="252067" data-toggle="help" href="#">
                <i class="help"></i>
              </a>
            </div>
          </article>
          {{/current}}
%endif
        </div>
      </div>
    </div>
  </article>
  {{/users}}
</script>

<script src="/js/vendor/require.js" data-main="/js/users.js">
</script>
