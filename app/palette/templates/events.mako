<section class="top-zone">
  <section class="row">
    <section class="col-xs-12">
      <h1 class="page-title">Events</h1>
      <!--
          <a href="#" class="alert errors"><span>0</span></a>
          <a href="#" class="alert warnings"><span>0</span></a>
	  -->
    </section>
  </section>
  <section class="row">
    <section class="col-xs-12 event-dropdowns">
      <div id="statuses-dropdown" class="btn-group"></div>
      <div id="types-dropdown" class="btn-group"></div>
      <div id="sites-dropdown" class="btn-group"></div>
      <div id="publishers-dropdown" class="btn-group"></div>
      <div id="projects-dropdown" class="btn-group"></div>
      <!-- TODO: Add back in Alpha 2 or later
      <div class="col-xs-4">
         <input class="form-control" type="text" placeholder="Workbook" style="margin-top:10px;">
      </div>
      -->

    </section>
  </section>
</section>
<section class="bottom-zone">
  <section id="event-list"></section>
</section>

<script id="event-list-template" type="x-tmpl-mustache">
  {{#events}}
  <article class="event">
    <div class="summary clearfix">
      <i class="fa fa-fw {{icon}} {{color}}"></i>
      <div>
	<h3>{{title}}</h3>
	<p>{{summary}}</p>
      </div>
      <i class="fa fa-fw fa-angle-down expand"></i>
    </div>
    <div class="description">{{{description}}}</div>
  </article>
  {{/events}}
</script>

<script id="event-dropdown-template" type="x-tmpl-mustache">
  <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown"><div>{{value}}</div><span class="caret"></span>
  </button>
  <ul class="dropdown-menu" role="menu">
    {{#options}}
    <li><a data-id="{{id}}">{{item}}</a></li>
    {{/options}}
  </ul>
</script>
