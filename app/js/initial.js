require(['jquery', 'configure', 'common', 'Dropdown', 'OnOff', 'bootstrap'],
function ($, configure, common, Dropdown, OnOff)
{
    var LICENSING_TIMEOUT = 3000; // 3 sec;
    var setupDone = false;

    var LICENSING_UNKNOWN = -1;
    var LICENSING_FAILED = 0;
    var LICENSING_OK = 1;

    var licensingState = LICENSING_UNKNOWN;

    /*
     * setPageError()
     * Set the main error reporting at the top and bottom of the page.
     */
    function setPageError(msg)
    {
        var html = '<h2 class="error">' + msg + '</h2>'
        $("section.top-zone").append(html);
        $("section.bottom-zone").prepend(html);
    }

    /*
     * setError()
     * Add an error message after the element specified by the selector.
     * Usually the selected element will be an input field.
     */
    function setError(selector, msg)
    {
        var html = '<p class="error">' + msg + '</p>';
        $(selector).after(html);
    }

    /*
     * gatherData()
     */
    function gatherData() {
        var data = {};
        data['license-key'] = $('#license-key').val();
        $.extend(data, configure.gatherURLData());
        $.extend(data, configure.gatherTableauURLData());
        $.extend(data, configure.gatherAdminData());
        $.extend(data, configure.gatherMailData());
        $.extend(data, configure.gatherTzData());
        return data;
    }

    /*
     * save_callback()
     * Callback when the save AJAX call was successfully sent to the server.
     * NOTE: the *data* may still have an error.
     */
    function save_callback(data) {
        if (data['status'] == 'OK') {
            window.location.replace("/");
            return;
        }

        var error = data['error'] || 'Unknown server error';
        setPageError(error);
    }

    /*
     * save()
     * Callback for the 'Save' button.
     */
    function save() {
        $('.error').remove();

        var data = {'action': 'save'}
        $.extend(data, gatherData());

        if (!validateForSave(data)) {
            setPageError("The page contains invalid input, please correct.");
            return;
        }

        $.ajax({
            type: 'POST',
            url: '/open/setup',
            data: data,
            dataType: 'json',

            success: save_callback,
            error: function (jqXHR, textStatus, errorThrown) {
                var msg = this.url + ": " + jqXHR.status + " (" + errorThrown + ")";
                setPageError(msg);
            }
        });
    }

    /*
     * testMail()
     * Callback for the 'Test Email' button.
     */
    function testMail() {
        $('.error').remove();
        $('#mail-test-message').html("");
        $('#mail-test-message').addClass('hidden');
        $('#mail-test-message').removeClass('green red');

        var data = {'action': 'test'}
        $.extend(data, configure.gatherMailData());
        data['test-email-recipient'] = $('#test-email-recipient').val();

        if (!validateForTest(data)) {
            return;
        }

        var result = {};
        $.ajax({
            type: 'POST',
            url: '/open/setup',  /* fixme - maybe /open/setup/mail? */
            data: data,
            dataType: 'json',
            async: false,

            success: function(data) {
                result = data;
            },
            error: function (jqXHR, textStatus, errorThrown) {
                alert(this.url + ": " +
                      jqXHR.status + " (" + errorThrown + ")");
            }
        });

        if (result['status'] == 'OK') {
            $('#mail-test-message').html("OK");
            $('#mail-test-message').addClass('green');
            $('#mail-test-message').removeClass('red hidden');
        } else {
            var html = 'FAILED';
            if (result['error'] != null && result['error'].length > 0) {
                html += ': ' + result['error'];
            }
            $('#mail-test-message').html(html);
            $('#mail-test-message').addClass('red');
            $('#mail-test-message').removeClass('green hidden');
        }
    }

    /*
     * validateAdminData(data)
     * FIXME: merge with configure.
     */
    function validateAdminData(data)
    {
        var result = true;

        var password = data['password'];
        if (password.length == 0) {
            setError("#password", "Password is required.");
            result = false;
        }
        var confirm_password = data['confirm-password'];
        if (confirm_password.length == 0) {
            setError("#confirm-password", "Confirmation password is required.");
            result = false;
        }
        if (result && (password != confirm_password)) {
            setError("#password", "Passwords must match.");
            result = false;
        }
        return result;
    }

    /*
     * validateMailData(data)
     */
    function validateMailData(data)
    {
        var result = true;

        var type = data['mail-server-type'];
        if (type == configure.MAIL_NONE) {
            /* Getting here implies mail server type changed. */
            return true;
        }

        if (!common.validEmail(data['alert-email-address'])) {
            setError("#alert-email-address", "The email address is invalid.");
            result = false;
        }

        if (type == configure.MAIL_DIRECT) {
            return result;
        }

        if (data['smtp-server'].length == 0) {
            setError("#smtp-server", "The mail server is required.");
            result = false;
        }

        var port = data['smtp-port'];
        if (port == null || port == 0) {
            setError("#smtp-port", "The port is required.");
            result = false;
        } else if (isNaN(port)) {
            setError("#smtp-port", "The port is invalid.");
            result = false;
        }

        /* SMTP username and password are optional */
        if (data['smtp-username'].length > 0
            && data['smtp-password'].length == 0) {
            setError("#smtp-password",
                     "The password is required when a username is specified.");
            result = false;
        } else if (data['smtp-username'].length == 0
                   && data['smtp-password'].length > 0) {
            setError("#smtp-username",
                     "The username is required when a password is specified.");
            result = false;
        }

        return result;
    }

    /*
     * validateForSave()
     * Test all input when the user presses the save button.
     */
    function validateForSave(data) {
        var result = true;

        if (!setupDone) {
            result = false;
        }
        if (!common.validURL(data['server-url'])) {
            setError("#server-url", "Invalid URL");
            result = false;
        }
        if (!common.validURL(data['tableau-server-url'])) {
            setError("#tableau-server-url", "Invalid URL");
            result = false;
        }
        if (data['license-key'].length < 2) { // FIXME //
            setError("#license-key", "Invalid license key");
            result = false;
        }
        if (!validateAdminData(data)) {
            result = false;
        }
        if (!validateMailData(data)) {
            result = false;
        }
        return result;
    }

    /*
     * validateForTest()
     * Validate the email setting when the user presses the test button.
     */
    function validateForTest(data) {
        var result = validateMailData(data);
        if (!common.validEmail(data['test-email-recipient'])) {
            /* put the error after the button */
            setError("#test-mail","Invalid email address");
            result = false;
        }
        return result;
    }

    function setup(data)
    {
        Dropdown.setupAll(data);
        OnOff.setup();

        $('#save').bind('click', save);
        $('#test-mail').bind('click', testMail);
        $('#test-mail').removeClass('disabled'); /* FIXME */

        $('#server-url').val(data['server-url']);
        $('#tableau-server-url').val(data['tableau-server-url']);
        $('#alert-email-name').val(data['alert-email-name']);
        $('#alert-email-address').val(data['alert-email-address']);
        $('#license-key').val(data['license-key']);

        $('#smtp-server').val(data['smtp-server']);
        $('#smtp-port').val(data['smtp-port']);
        $('#smtp-username').val(data['smtp-username']);
        $('#smtp-password').val(data['smtp-password']);

        /* layout changes based on selections */
        Dropdown.setCallback(function () {
            configure.changeMail();
        }, '#mail-server-type');
        configure.changeMail();

        /* help */
        configure.lightbox(236535, 'Palette Server URL');
        configure.lightbox(237794, 'Tableau Server URL');
        configure.lightbox(237795, 'License Key');
        configure.lightbox(236536, 'Palette Admin Password');
        configure.lightbox(252063, 'Tableau Server Repository Database User Password');
        configure.lightbox(236542, 'Mail Server');
        configure.lightbox(236544, 'Authentication');
        configure.lightbox(237785, 'Timezone');

        $(".version").html(data['version']);

        setupDone = true;
    }

    /*
     * licensingQuery()
     */
    function licensingQuery()
    {
        $.ajax({
            url: '/licensing',
            success: function(data) {
                $().ready(function() {
                    /* implicity cancels licensingTryMsgTimeout */
                    $("div.licensing").remove();
                    $("body > div").removeClass("hidden");
                });
            },
            error: function (jqXHR, textStatus, errorThrown) {
                $().ready(function() {
                    $("div.licensing.status").remove();
                    $("div.licensing.error").removeClass("hidden");
                    setTimeout(licensingQuery, LICENSING_TIMEOUT);
                });
            }
        });
    }

    /* Ensure that the server can talk to licensing. */
    licensingQuery();
    /* Display a status message after half a second if not already compete. */
    $().ready(function() {
        setTimeout(function () {
            $("div.licensing.status").removeClass("hidden");
        }, 500); /* half second? */
    });

    /* fill in initial values */
    $.ajax({
        url: '/open/setup',
        success: function(data) {
            $().ready(function() {
                setup(data);
            });
        },
        error: function (jqXHR, textStatus, errorThrown) {
            setPageError("Your browser is disconnected.");
        }
    });
});
