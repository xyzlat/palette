<nav id="mainNav" data-topbar>
  <div class="container">
    <a class="site-id" href="/"></a>
    <span id="toggle-main-menu" class="fi-list"></span>
    <ul class="nav">
      <li class="more">
        <a href="/support/ticket"><i class="fa fa-question-circle"></i>
	  <span>Help</span>
	</a>
        <ul>
          <li>
            <a href="/support/contact">
              <i class="fa fa-fw fa-mail-forward"></i> Contact Support
            </a>
          </li>
          <li>
            <a href="http://www.tableausoftware.com/support/help">
              <i class="fa fa-fw fa-book"></i> Tableau Docs
            </a>
          </li>
          <li>
            <a href="/support/about">
              <i class="fa fa-fw fa-info-circle"></i> About Palette
            </a>
          </li>
        </ul>
      </li>

      <li class="more">
        <a id="profile-link" href="/profile">
          <i class="fa fa-user"></i> 
          <span>${req.remote_user.friendly_name}
          (${req.remote_user.role.name})</span>
        </a>
        <ul>
          <li>
            <a href="/profile">
              <i class="fa fa-fw fa-user"></i> Edit Profile
            </a>
          </li>
          <li>
            <a href="/logout">
              <i class="fa fa-fw fa-sign-out"></i> Log out
            </a>
          </li>
        </ul>
      </li>
    </ul>
  </div>
</nav>
