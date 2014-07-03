# -*- coding: utf-8 -*-
<%inherit file="layout.mako" />

<%block name="title">
<title>About Palette</title>
</%block>

<section class="dynamic-content about-page">
  <h1 class="page-title">About Palette</h1>

  <h2>Version ${obj.version}</h2>
  <div>
    <p>&copy; 2014 Palette Software</p>
    <p>License Key </p>
    <p>The use of this product is subject to the terms of the Palette End User Agreement, unless other specified therein.</p>
  </div>

  <h2>Palette Software</h2>
  <div>
    <p>156 2nd Street</p>
    <p>San Francisco, California 94105</p>
  </div>

  <h2>Contact</h2>
  <div>
    <p>hello@palette-software.com</p>
    <p>www.palette-software.com</p>
  </div>
</section>

<script src="/app/module/palette/js/vendor/require.js" data-main="/app/module/palette/js/contact.js">
</script>
</html>

