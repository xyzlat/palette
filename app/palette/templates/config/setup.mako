# -*- coding: utf-8 -*-
<%inherit file="../layout.mako" />

<%block name="title">
<title>Palette - Setup Configuration</title>
</%block>

<div class="dynamic-content configuration setup-page">
  <div class="scrollable">

    <a name="url"></a>
    <section class="top-zone">
      <section class="row">
        <section class="col-xs-12">
          <h1 class="page-title">Setup Configuration</h1>
        </section>
      </section>
    </section>
    <section>
      <h2>Palette Server URL</h2>
      <p>This is the domain name url that you will type into your browser to view your Palette Server</p>
      <input type="text" id="server-url" />
      <div class="save-cancel">
        <button type="button" id="save-url" class="btn btn-primary disabled">
          Save
        </button>
        <button type="button" id="cancel-url" class="btn btn-primary disabled">
          Cancel
        </button>
      </div>
    </section>

    <a name="admin"></a>
    <hr />
    <section id="admin">
      <h2>Palette Admin Password</h2>
      <p>You will use this password to login to your Palette Server using the "Palette" username</p>
      <h3>Password *</h3>
      <input type="password" id="password" />
      <!--<label for="password">&nbsp;</label>-->
      <h3>Confirm Password *</h3>
      <input type="password" id="confirm-password" />
      <!--<label for="confirm-password">&nbsp;</label>-->
      <div class="save-cancel">
        <button type="button" id="save-admin" class="btn btn-primary disabled">
          Save
        </button>
        <button type="button" id="cancel-admin" class="btn btn-primary disabled">
          Cancel
        </button>
      </div>
    </section>

    <a name="mail"></a>
    <hr />
    <section id="mail">
      <h2>Mail Server</h2>
      <p>The Palette Server will send you alerts using this mail server and email address</p>
      <%include file="mail.mako" />
      <div class="save-cancel">
        <button type="button" id="save-mail" class="btn btn-primary disabled">
          Save
        </button>
        <button type="button" id="cancel-mail" class="btn btn-primary disabled">
          Cancel
        </button>
      </div>
    </section>

    <a name="ssl"></a>
    <hr />
    <section id="ssl">
      <h2>Server SSL Certificate</h2>
      <h3>SSL Certificate File</h3>
      <p>Must be a valid PEM-encoded x509 certificate with the extension .crt</p>
      <textarea id="ssl-certificate-file"></textarea>
      <h3>SSL Certificate Key File</h3>
      <p>Must be a valid RSA or DSA key that is not password protected with the file extension .key</p>
      <textarea id="ssl-certificate-key-file"></textarea>
      <h3>SSL Certificate Chain File (Optional)</h3>
      <p>Some certificate providers issue two certificate files.  The second certificate is a chain file, which is a concatenation of all the certificates that from the certificate chain for the server certificate.  All certificates in the file must be x509 PEM-encoded and the file must have a .crt extension (not .pem)</p>
      <textarea id="ssl-certificate-chain-file"></textarea>
      <div class="save-cancel">
        <button type="button" id="save-ssl" class="btn btn-primary">
          Save
        </button>
        <button type="button" id="cancel-ssl" class="btn btn-primary">
          Cancel
        </button>
      </div>
    </section>

    <a name="auth"></a>
    <hr />
    <section id="auth">
      <h2>Authentication</h2>
      <p>
        <span id="authentication-type" class="btn-group"></span>
      </p>
      <div class="save-cancel">
        <button type="button" id="save-auth" class="btn btn-primary">
          Save
        </button>
        <button type="button" id="cancel-auth" class="btn btn-primary">
          Cancel
        </button>
      </div>
    </section>
  </div>
</div>

<script id="dropdown-template" type="x-tmpl-mustache">
  <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown"><div data-id="{{id}}">{{value}}</div><span class="caret"></span>
  </button>
  <ul class="dropdown-menu" role="menu">
    {{#options}}
    <li><a data-id="{{id}}">{{item}}</a></li>
    {{/options}}
  </ul>
</script>

<script src="/app/module/palette/js/vendor/require.js" data-main="/app/module/palette/js/setup.js">
</script>
