# -*- coding: utf-8 -*-
<a id="236543" data-toggle="help" href="#"><i class="help"></i></a>
<h2>Server SSL Certificate</h2>
<section class="slider-group">
  <div>
    <div>Custom SSL</div>
    <span id="enable-ssl" class="onoffswitch"></span>
  </div>
</section>
<p>If your Palette Server is self-hosted we recommend that you enable Custom SSL.</p>
<div class="settings hidden">
  <h3>SSL Certificate File *</h3>
  <p>Must be a valid PEM-encoded x509 certificate with the extension .crt.</p>
  <textarea id="ssl-certificate-file"></textarea>
  <h3>SSL Certificate Key File *</h3>
  <p>Must be a valid RSA or DSA key that is not password protected with the file extension .key.</p>
  <textarea id="ssl-certificate-key-file"></textarea>
  <h3>SSL Certificate Chain File</h3>
  <p>Some certificate providers issue two certificate files.  The second certificate is a chain file, which is a concatenation of all the certificates that from the certificate chain for the server certificate.  All certificates in the file must be x509 PEM-encoded and the file must have a .crt extension (not .pem).</p>
  <textarea id="ssl-certificate-chain-file"></textarea>
</div>
