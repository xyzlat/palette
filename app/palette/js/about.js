require(['jquery', 'topic', 'common'],
function ($, topic, common)
{
    /*
     * restartWebserver()
     */
    function restartWebserver() {        
        $.ajax({
            type: 'POST',
            url: '/rest/manage',
            data: {'action': 'restart-webserver'},
            dataType: 'json',
            async: false,
            
            success: function(data) {
                $('#restart-webserver').addClass('disabled');
            },
            error: common.ajaxError,
        });
    }

    /*
     * restartController()
     */
    function restartController() {
        $.ajax({
            type: 'POST',
            url: '/rest/manage',
            data: {'action': 'restart-controller'},
            dataType: 'json',
            async: false,
            
            success: function(data) {
                $('#restart-controller').addClass('disabled');

                /* If there are no agents connected, then there will be no
                 * state change - re-enabled the 'Restart Controller' button
                 * after a timeout regardless. */
                setTimeout(function () {
                    $('#restart-controller').removeClass('disabled');
                }, 10000);
            },
            error: common.ajaxError,
        });
    }

    topic.subscribe('state', function(message, data) {
        if (data['connected']) {
            $('#restart-webserver').removeClass('disabled');
            $('#restart-controller').removeClass('disabled');
        }
    });

    common.startMonitor(false);
    common.setupOkCancel();

    $().ready(function() {
        $('#restart-webserver').data('callback', restartWebserver);
        $('#restart-controller').data('callback', restartController);
    });
});