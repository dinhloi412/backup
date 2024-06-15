odoo.define('your_module.year_widget', function (require) {
    "use strict";

    var core = require('web.core');
    var FieldDatetime = core.form_widget_registry.get('datetime');
    var Datepicker = core.datepicker.Datepicker;
    var utils = require('web.utils');

    var YearPicker = FieldDatetime.extend({
        template: 'FieldDatetime',

        _renderReadonly: function () {
            this.$el.text(this._formatValue(this.value));
        },

        _renderEdit: function () {
            var self = this;
            var $input = this.$('input');
            if ($input.length) {
                $input.datepicker('destroy');
            }
            $input = $('<input>').appendTo(this.$el).datepicker({
                autoclose: true,
                format: "yyyy",
                viewMode: "years",
                minViewMode: "years"
            }).on('changeDate', function (ev) {
                self._setValue(ev.date);
            });
            this.$input = $input;
            this.$input.val(this._formatValue(this.value));
        }
    });

    core.form_widget_registry.add('year', YearPicker);

    return YearPicker;
});
