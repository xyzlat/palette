# -*- coding: utf-8 -*-
<%inherit file="layout.mako" />

<%block name="title">
<title>Palette - User Configuration</title>
</%block>

<style>
h2 {
  text-transform: uppercase;
}
</style>

<section class="dynamic-content">
  <section class="top-zone">
    <section class="row">
      <section class="col-xs-12">
        <h1 class="page-title">Amazon Web Services S3</h1>
      </section>
    </section>
    <section class="row">
      <section class="col-xs-12">
         <p>Cloud storage to save your Tableau backups, logfiles, workbooks and other Palette generated files</p>
         <h2>Credentials</h2>
         <h3>Access Key ID</h3>
         <p class="editbox" data-href="/rest/s3/access-key">
           ${obj.access_key}
         </p>
         <h3>Secret Access Key</h3>
         <p class="editbox" data-href="/rest/s3/secret">
           ${obj.secret}
         </p>
         <h3>Bucket Name</h3>
         <p class="editbox" data-href="/rest/s3/bucket">
           ${obj.bucket}
         </p>
      </section>
    </section>
    </section>
  </section>
</section>

<script src="/app/module/palette/js/vendor/require.js" data-main="/app/module/palette/js/s3.js">
</script>