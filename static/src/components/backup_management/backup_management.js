/** @odoo-module **/


const { Component, useState, onWillStart, useRef } = owl;
import { useService } from "@web/core/utils/hooks";


export class BackupManagement extends Component {
    setup() {
        this.orm = useService("orm")
        onWillStart(async ()=>{
            await this.getAllTasks()
        })
    }
}

BackupManagement.template = 'backup.BackupManagement'
registry.category('actions').add('backup.backup_management_js', BackupManagement);
