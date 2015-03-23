require(['jquery', 'topic', 'template', 'common', 'items',
         'Dropdown', 'OnOff', 'bootstrap'],
        function ($, topic, template, common, items, Dropdown, OnOff)
{
    var LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

    var active = false;
    var refresh_unavailable_text = 'Refresh not currently possible.';

    var startswith = null;
    var counts = null;

    function ddCallback(node, value) {
        var $section = $(node).closest('article');
        var old = $('.display-role', $section).html();
        if (/Publisher/i.test(old)) {
            if (value.toLowerCase() == 'none') {
                value = 'Publisher';
            } else {
                value = 'Publisher & ' + value;
            }
        }
        $('.display-role', $section).html(value);
    }

    function setup_letters() {
        
        var html = '';
        if (total <= 100) {
            html = '<a>All</a>';
        }
	    for(var i=0; i<LETTERS.length; i++)
	    {
            var letter = LETTERS.charAt(i);
            if (!(letter in counts)) {
                continue;
            }
            if (html.length > 0) {
                html += "&nbsp;:\n";
            }
	        html += "<a>" + LETTERS.charAt(i) + "</a>";
        }
        $('.letters').html(html + "\n");
        $('.letters a').bind('click', function() {
            query($(this).html());
        });
    }

    function update(data) {
        $().ready(function() {
            var t = $('#user-list-template').html();
            var rendered = template.render(t, data);
            $('#user-list').html(rendered);
            
            counts = data['counts']
            total = counts['__total__']
            setup_letters();
            items.bind();
            Dropdown.bind('.admin-type', data['admin-levels'], ddCallback);
            $('.admin-type').each(function() {
                var dd = $(this).data();
                dd.set(parseInt(dd.original_html));
            });
            OnOff.setup();
            var last_update = data['last-update']
            if (last_update != null) {
                $('#last-update').html(last_update);
                $('.refresh').show();
            }
        });
    }

    function refresh() {
        $.ajax({
            type: 'POST',
            url: '/rest/users',
            data: {'action': 'refresh'},
            dataType: 'json',
            async: false,

            success: function(data) {
                update(data);
            },
            error: common.ajaxError,
        });
    }

    function bind_refresh() {
        $('.refresh > p > i').bind('click', function() {
            if (active) {
                refresh();
            }
        });
    }

    function query(val) {
        var url = '/rest/users';
        if (val != null && val.toLowerCase() != 'all') {
            url += '?startswith=' + val;
        }
        $.ajax({
            url: url,
            success: function(data) {
                if (val != null && val.toLowerCase() != 'all') {
                    startswith = val;
                }
                update(data);
            },
            error: common.ajaxError,
        });
    }

    topic.subscribe('state', function(message, data) {
        $().ready(function() {
            var allowed = data['allowable-actions'];
            if ($.inArray('user-refresh', allowed) >= 0) {
                $('.refresh > p > i').removeClass('inactive');
                $('.refresh > p > span.message').html('');
                active = true;
                bind_refresh();
            } else {
                $('.refresh > p > i').addClass('inactive');
                $('.refresh > p > i').off('click');
                $('.refresh > p > span.message').html(refresh_unavailable_text);
                active = false;
            }
        });
    });

    common.startMonitor(false);
    query();
});