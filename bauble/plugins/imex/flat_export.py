# -*- coding: utf-8 -*-
#
# Copyright 2008, 2009, 2010 Brett Adams
# Copyright 2018 Mario Frasca <mario@anche.no>.
#
# This file is part of ghini.desktop.
#
# ghini.desktop is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ghini.desktop is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ghini.desktop. If not, see <http://www.gnu.org/licenses/>.


from gi.repository import Gtk
import os.path
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.types import Integer, Boolean, Float
import bauble
from bauble.search import MapperSearch
from bauble.editor import (
    GenericEditorView, GenericEditorPresenter)
from bauble import paths, pluginmgr
from bauble.querybuilder import SchemaMenu


class FlatFileExporter(GenericEditorPresenter):

    view_accept_buttons = ['cancel_button', 'confirm_button']

    def __init__(self, view=None):
        super().__init__(model=self, view=view, refresh_view=False)

        self.domain_map = MapperSearch.get_domain_classes().copy()
        self.domain = None
        self.mapper = None

        self.view.widgets.domain_ls.clear()
        for key in sorted(self.domain_map.keys()):
            self.view.widgets.domain_ls.append([key])
        self.signal_id = None

    def on_schema_menu_activated(self, menuitem, clause_field, prop):
        """add the selected item to the exported fields

        """
        self.view.widgets.exported_fields_ls.append((clause_field, ))

    def set_model_fields(self, output_file=None, domain=None,
                         exported_fields=None, 
                         **kwargs):
        if kwargs:
            logger.warning('set_model_fields received extra parameters %s' % kwargs)

        self.view.widget_set_value('output_file', output_file)

        self.view.widget_set_value('domain_combo', domain)
        self.domain = domain

        self.view.widgets.exported_fields_ls.clear()
        for i in exported_fields:
            self.view.widgets.exported_fields_ls.append((i, ))

    def on_domain_combo_changed(self, *args):
        """
        Change the search domain.  Resets the expression table and
        deletes all the expression rows.
        """
        try:
            index = self.view.widgets.domain_combo.get_active()
        except AttributeError:
            return
        if index == -1:
            return

        self.domain = self.view.widgets.domain_ls[index][0]
        self.view.widgets.exported_fields_ls.clear()
        self.mapper = class_mapper(self.domain_map[self.domain])

        def on_prop_button_clicked(button, event, menu):
            menu.popup(None, None, None, None, event.button, event.time)

        def relation_filter(container, prop):
            if isinstance(prop, ColumnProperty):
                column = prop.columns[0]
                if isinstance(column.type, bauble.btypes.Date):
                    return False
                if column.name.endswith('_id'):
                    return False
                if container is None:
                    return True
                if not container.uselist:
                    return True
                if not isinstance(column.type, (Integer, Float, Boolean)):
                    return False
            else:
                if container is None:
                    return True
                if prop.mapper == container.parent:
                    return False
            return True

        self.schema_menu = SchemaMenu(self.mapper,
                                      self.on_schema_menu_activated,
                                      relation_filter)
        if self.signal_id is not None:
            self.view.widgets.chooser_btn.disconnect(self.signal_id)
        self.signal_id = self.view.widgets.chooser_btn.connect('button-press-event', on_prop_button_clicked,
                                                               self.schema_menu)


class FlatFileExportTool(pluginmgr.Tool):
    category = _('Export')
    label = _('Flat file (csv)')

    @classmethod
    def start(cls):
        gladefilepath = os.path.join(paths.lib_dir(), "plugins", "imex", "flat_export.glade")
        view = GenericEditorView(
            gladefilepath,
            parent=None,
            root_widget_name='main_dialog')
        qb = FlatFileExporter(view)
        qb.set_model_fields(output_file='/tmp/test.csv', domain='plant',
                            exported_fields=['accession.code', 'code', 'accession.species.genus.epithet', 'accession.species.epithet'])
        response = qb.start()
        if response == Gtk.ResponseType.OK:
            query = qb.do_export()
        qb.cleanup()

