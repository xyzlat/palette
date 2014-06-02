/* 
 * FIXME: This code will likely be run from the layout or side-bar
 * templates and should be named accordingly.
 */

define(['jquery', 'topic'],
function ($, topic)
{

    function clearmenu() {
	    $('.main-side-bar, .secondary-side-bar, .dynamic-content').removeClass('open');
	    $('.main-side-bar, .secondary-side-bar, .dynamic-content').removeClass('collapsed');
	    $('#mainNav .container > i').removeClass('open');
    }

    /*
     * bindEvents()
     * Expand/contract the individual events on user click.
     * NOTE: Must be run after the AJAX request which populates the list.
     */
    function bindEvents() {
        $('.event > div.summary').bind('click', function() {
            $(this).parent().toggleClass('open');
            $(this).find('i.expand').toggleClass("fa-angle-up fa-angle-down");
        });
    }

    /*
     * setupEvents()
     * Initialize the static page elements related to event handling.
     */
    function setupEvents()
    {
        $('#toggle-event-filters').bind('click', function() {
            $(this).toggleClass('open');
            $('.top-zone').find('.btn-group').toggleClass('visible');
        });

        $(function(){
            $('.dynamic-content').bind('click', function() {
                var viewport = $(window).width();
                var dynamicClosed = $(this).hasClass('closed');
                if (viewport <= 960 && dynamicClosed != true) {
                    clearmenu();
                    $('.secondary-side-bar, .dynamic-content').toggleClass('closed');
                    $('#toggle-events').toggleClass('active');
                }
            }); 
        });

        $(function(){
            $('.secondary-side-bar').bind('click', function() {
                var viewport = $(window).width();
                var dynamicClosed = $(this).hasClass('closed');
                if (viewport <= 960 && dynamicClosed == true) {
                    clearmenu();
                    $('.secondary-side-bar, .dynamic-content').toggleClass('closed');
                    $('#toggle-events').toggleClass('active');
                }
            }); 
        });

        $(function(){
            $('#toggle-events').bind('click', function() {
                clearmenu();
                $('.secondary-side-bar, .dynamic-content').toggleClass('closed');
                $(this).toggleClass('active');
            }); 
        });
    }

    /*
     * setupDialogs()
     * Connect dialogs to their relevant click handlers.
     */
    function setupDialogs()
    {
        $('a.popup-link').bind('click', function() {
            var popupLink = $(this).hasClass('inactive');
            if (popupLink == false) {
                $('article.popup').removeClass('visible');
                var popTarget = $(this).attr('name');
                $('article.popup#'+popTarget).addClass('visible');
            }
        });
    }

    /*
     * setupDropdowns()
     * Enable the select-like elements created with the dropdown class.
     */
    function setupDropdowns() {
        $('.dropdown-menu li').bind('click', function(event) {
            event.preventDefault();
            var a = $(this).find('a');
            var div =  $(this).parent().siblings().find('div')
            var href = a.attr('href');
            if (!href || href == '#') {
                div.text(a.text());
                return;
            }
            data = customDataAttributes(a);
            $.ajax({
                type: 'POST',
                url: href,
                data: data,
                dataType: 'json',
                async: false,
            
                success: function(data) {
                    div.text(a.text());
                },
                error: function(req, textStatus, errorThrown) {
                    alert(textStatus + ": " + errorThrown);
                }
            });
        });
    }

    /*
     * setupConfigure
     * Enable the configure expansion item on main sidebar.
     */
    function setupCategories() {
        $('.expand').parent().bind('click', function(event) {
            event.preventDefault();
            if ($('.expand', this).hasClass('fa-angle-down')) {
                $('.expand', this).removeClass('fa-angle-down');
                $('.expand', this).addClass('fa-angle-up');
                $(this).parent().find('ul').addClass('visible');
            } else {
                $('.expand', this).removeClass('fa-angle-up');
                $('.expand', this).addClass('fa-angle-down');
                $(this).parent().find('ul').removeClass('visible');
            }                
        });
    }

    /*
     * customDataAttributes
     * Return the HTML5 custom data attributes for a selector or domNode.
     */
    function customDataAttributes(obj) {
        if (obj instanceof $) {
            obj = obj.get(0);
        }
        var d = {}
        for (var i=0, attrs=obj.attributes, l=attrs.length; i<l; i++){
            var name = attrs.item(i).nodeName;
            if (!name.match('^data-')) {
                continue;
            }
            d[name.substring(5)] = attrs.item(i).nodeValue;
        }
        return d;
    }

    /* MONITOR TIMER */
    var interval = 1000; //ms - FIXME: make configurable from the backend.
    var current = null;

    function update(data)
    {
        var state = data['state']
        var json = JSON.stringify(data);
        
        /*
         * Broadcast the state change, if applicable.
         * NOTE: this method may lead to false positive, which is OK.
         */
        if (json != current) {
            topic.publish('state', data);
            current = json;
        }

        var text = 'ERROR';
        if (data.hasOwnProperty('text') && data['text'] != 'none') {
            text = data['text'];
        }
        $('#status-text').html(text);

        var color = 'red';
        if (data.hasOwnProperty('color') && data['color'] != 'none') {
            color = data['color'];
        }
        var src = '/app/module/palette/images/status-'+color+'-light.png';
        $('#status-image').attr('src', src);
        //$('#status-text').attr("class", color);
    }

    function poll() {
        $.ajax({
            url: '/rest/monitor',
            success: function(data) {
                update(data);
            },
            error: function(req, textStatus, errorThrown)
            {
                var data = {}
                data['text'] = textStatus;
                update(data);
            },
            complete: function() {
                setTimeout(poll, interval);
            }
        });
    }

    function startup() {

        /* MOBILE TITLE */
        $(function(){
            var pageTitle = $('title').text();
            pageTitle = pageTitle.replace('Palette - ', '');
        
            $('.mobile-title').text(pageTitle);
        });

        $('.popup-close, article.popup .shade').bind('click', function() {
            $('article.popup').removeClass('visible');
        });

        /* SERVER LIST */
        $('.server-list li a').bind('click', function() {
            $(this).toggleClass('visible');
            $(this).parent().find('ul.processes').toggleClass('visible');
        });

        $('#mainNav .container > i').bind('click', function() {
            $('.main-side-bar, .secondary-side-bar, .dynamic-content').toggleClass('open');
	        $(this).toggleClass('open');
        });

        /* HEADER POPUP MENUS */
        var viewport = $(window).width();

        $('#mainNav ul.nav li.more').bind('mouseenter', function() {
            if (viewport >= 960) {
        	    $('#mainNav ul.nav li.more ul').removeClass('visible');
                $(this).find('ul').addClass('visible');
            }
        });
        $('#mainNav ul.nav li.more').bind('mouseleave', function() {
            if (viewport >= 960) {
                $(this).find('ul').removeClass('visible');
            }
        });     
        
        $('#mainNav ul.nav li.more a').bind('click', function() {
            if (viewport <= 960) {
                event.preventDefault();
            }

        });

        $('#mainNav ul.nav li.more').bind('click', function() {
            if (viewport <= 960) {
                var navOpen = $(this).find('ul').hasClass('visible'); 
                $('#mainNav ul.nav li.more').find('ul').removeClass('visible');
                if (navOpen) {
                    $(this).find('ul').removeClass('visible');
                }
                else {
                    $(this).find('ul').addClass('visible');
                }           
            } 
        });

        setupEvents();
        /* FIXME: run after AJAX */
        bindEvents();
        
        setupCategories();

        /* 
         * Start a timer that periodically polls the status every
         * 'interval' milliseconds
         */
        poll();
    }

    return {'state': current,
            'startup': startup,
            'bindEvents': bindEvents,
            'setupDialogs': setupDialogs,
            'setupDropdowns' : setupDropdowns
           };
});
