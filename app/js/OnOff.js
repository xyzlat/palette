define(['jquery', 'plugin'],
       function($, plugin) {

    function str2bool(val) {
        if (val == null) return false;
        val = val.trim().toLowerCase();
	    switch(val){
		case "true": case "yes": case "1": case "checked": return true;
		case "false": case "no": case "0": return false;
		default: return false;
	    }
    }

    function OnOff(node, callback) {
        this.node = node;
        this.callback = callback;
        this.id = $(node).attr('data-id');
        this.name = $(node).attr('data-name');
        this.href = $(node).attr('data-href');

        var data = {'name': this.name}

        var value = str2bool($(node).html());
        if (value) {
            data['checked'] = 'checked';
        }

        $(node).render('onoffswitch', data);

        this.change = function () {
            var checked = $('input[type="checkbox"]', this.node).prop("checked");
            var data = {'value':!checked}
            if (this.id != null) {
                data['id'] = this.id;
            }
            if (this.name != null) {
                data['name'] = this.name;
            }
            var success;

            if (this.href) {
                $.ajax({
                    type: 'POST',
                    url: this.href,
                    data: data,
                    dataType: 'json',
                    async: false,

                    success: function(data) {
                        success = true;
                    },
                    error: function (jqXHR, textStatus, errorThrown) {
                        alert(this.url + ": " +
                              jqXHR.status + " (" + errorThrown + ")");
                        sucess = false;
                    }
                });
            } else {
                success = true;
            }

            if (success) {
                $('input[type="checkbox"]', this.node).prop("checked", !checked);
                if (this.callback) {
                    this.callback(!checked);
                }
            }
        }

        $(this.node).bind('click', function(event) {
            event.stopPropagation();
            $(this).data().change();
        });
    }

    OnOff.bind2 = function(selector, callback)
    {
        var array = [];
        $(selector).each(function() {
            var obj = new OnOff($(this).get(0), callback);
            $(this).data(obj);
            array.push(obj);
        });
        if (array.length == 0) return null;
        return array.length > 1 ? array : array[0];
    }

    OnOff.setup = function(callback)
    {
        OnOff.bind2('.onoffswitch', callback); // FIXME
    }

    OnOff.getValueById = function(id)
    {
        return $('#'+id+' .onoffswitch-checkbox').prop("checked");
    }

    OnOff.setValueById = function(id, value)
    {
        var onoff = $('#'+id+' .onoffswitch-checkbox');
        onoff.prop("checked", value);
    }

    OnOff.setCallback = function(callback, selector)
    {
        if (selector == null) {
            selector = '.onoffswitch';
        }
        $(selector).each(function (index) {
            var onoff = $(this).data();
            onoff.callback = callback;
        });
    }

    return OnOff;
});
