# -*- coding: utf-8 -*-
#
# Copyright 2015 Mario Frasca <mario@anche.no>.
#
# This file is part of bauble.classic.
#
# bauble.classic is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# bauble.classic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with bauble.classic. If not, see <http://www.gnu.org/licenses/>.

import os
import logging
logger = logging.getLogger(__name__)
from bauble import paths, pluginmgr, utils
from bauble.plugins.plants import Species
from bauble.i18n import _
import pango


from bauble.editor import (
    GenericEditorView, GenericEditorPresenter)


def start_taxonomy_check():
    '''run the batch taxonomy check (BTC)
    '''

    view = GenericEditorView(
        os.path.join(paths.lib_dir(), 'plugins', 'plants',
                     'taxonomy_check.glade'),
        parent=None,
        root_widget_name='dialog1')
    model = type('BTCStatus', (object,), {})()
    model.page = 1
    model.selection = view.get_selection()
    model.tick_off = None
    model.report = None
    model.file_path = '/home/mario/Downloads/tnrs_results.txt'

    if model.selection is None:
        return
    presenter = BatchTaxonomicCheckPresenter(model, view, refresh_view=True)
    error_state = presenter.start()
    if error_state:
        print 'will rollback'
        presenter.session.rollback()
    else:
        print 'will commit'
        presenter.commit_changes()
        from bauble import gui, view
        search_view = gui.get_view()
        if isinstance(search_view, view.SearchView):
            search_view.reset_view()
    presenter.session.close()
    presenter.cleanup()
    return error_state


def species_to_fix(ssn, binomial, author, create=False):
    binomial = utils.to_unicode(binomial)
    author = utils.to_unicode(author)
    gen_epithet, sp_epithet = binomial.split(' ', 1)
    return Species.retrieve_or_create(
        ssn, {'object': 'taxon',
              'rank': 'species',
              'ht-epithet': gen_epithet,
              'epithet': sp_epithet,
              'ht-rank': 'genus',
              'author': author},
        create=create)


ACCEPTABLE = 0
STOCK_ID = 1
OLD_BINOMIAL = 2
NEW_BINOMIAL = 3
AUTHORSHIP = 4
TAXON_STATUS = 5
ACCEPTED_BINOMIAL = 6
ACCEPTED_AUTHORSHIP = 7
TO_PROCESS = 8

YES_ICON = 'gtk-yes'
NO_ICON = 'gtk-no'


class BatchTaxonomicCheckPresenter(GenericEditorPresenter):
    '''
    the batch taxonomy check (BTC) can run if you have an equal rank
    selection of taxa in your search results. The BTC exports the names
    to the clipboard and opens the browser on the
    http://tnrs.iplantcollaborative.org/TNRSapp.html page.

    the user will run the service on the remote site, then save the results to
    a file. then back to Bauble's BTC, the user will open the file and finally
    interact with the BTC view.

    the Model of the BTC is a list of tuples.

    '''

    widget_to_field_map = {'file_path_entry': 'file_path'}
    view_accept_buttons = ['ok_button']

    def __init__(self, *args, **kwargs):
        super(BatchTaxonomicCheckPresenter, self).__init__(*args, **kwargs)
        self.refresh_visible_frame()
        self.tick_off_list = self.view.widgets.liststore2
        self.binomials = [item.str(item, remove_zws=True)
                          for item in self.model.selection
                          if isinstance(item, Species) and item.sp != '']

    def refresh_visible_frame(self):
        for i in range(1, 4):
            frame_id = 'frame%d' % i
            self.view.widget_set_visible(frame_id, i == self.model.page)

    def on_frame1_next(self, *args):
        'parse the results into the liststore2 and move to frame 2'
        responses = []
        self.tick_off_list.clear()
        import codecs
        with codecs.open(self.model.file_path, 'r', 'utf16') as f:
            keys = f.readline().strip().split('\t')
            for l in f.readlines():
                l = l.strip()
                values = [i.strip() for i in l.split("\t")]
                responses.append(dict(zip(keys, values)))
        for binomial, response in zip(self.binomials, responses):
            acceptable = response['Name_matched_rank'] == u'species'
            row = [acceptable,
                   acceptable and YES_ICON or NO_ICON,
                   binomial]
            for key in ['Name_matched', 'Name_matched_author',
                        'Taxonomic_status', 'Accepted_name',
                        'Accepted_name_author']:
                row.append(response[key])
            row.append(acceptable)
            self.tick_off_list.append(row)
            if response['Taxonomic_status'] == 'Synonym':
                row = [True, YES_ICON, '', response['Accepted_name'],
                       response['Accepted_name_author'], 'Accepted',
                       '', '', True]
                self.tick_off_list.append(row)
        self.on_frame_next(*args)

    def on_frame2_next(self, *args):
        'execute all that is selected in liststore2 and move to frame 3'
        self.on_frame_next(*args)
        tb = self.view.widgets.textbuffer3
        bold = tb.create_tag(None, weight=pango.WEIGHT_BOLD)
        tb.set_text('')

        for row in self.tick_off_list:
            if row[TO_PROCESS] is False:
                tb.insert_at_cursor("skipping %s\n" %
                                    (row[OLD_BINOMIAL] or row[NEW_BINOMIAL]))
                continue
            if row[OLD_BINOMIAL] == '':
                tb.insert_with_tags(tb.get_end_iter(),
                                    "new taxon %s" % row[NEW_BINOMIAL],
                                    bold)
                obj = species_to_fix(
                    self.session, row[NEW_BINOMIAL], row[AUTHORSHIP],
                    create=True)
            else:
                tb.insert_with_tags(tb.get_end_iter(),
                                    "update taxon %s" % row[OLD_BINOMIAL],
                                    bold)
                if row[TAXON_STATUS] == 'Synonym':
                    accepted = species_to_fix(
                        self.session, row[ACCEPTED_BINOMIAL],
                        row[ACCEPTED_AUTHORSHIP],
                        create=True)
                else:
                    accepted = None
                obj = species_to_fix(
                    self.session, row[OLD_BINOMIAL], row[AUTHORSHIP],
                    create=False)
                gen_epithet, sp_epithet = utils.to_unicode(
                    row[NEW_BINOMIAL]).split(' ', 1)
                obj.genus.genus = gen_epithet
                obj.sp = sp_epithet
                if accepted:
                    obj.accepted = accepted
            tb.insert_with_tags(tb.get_end_iter(),
                                " %s\n" % row[AUTHORSHIP],
                                bold)

    def on_frame_next(self, *args):
        self.model.page += 1
        self.refresh_visible_frame()

    def on_frame_previous(self, *args):
        self.model.page -= 1
        self.refresh_visible_frame()

    def on_copy_to_clipboard_button_clicked(self, *args):
        text = '\n'.join(self.binomials)
        import gtk
        clipboard = gtk.Clipboard()
        clipboard.set_text(text)

    def on_tnrs_browse_button_clicked(self, *args):
        from bauble.utils import desktop
        desktop.open('http://tnrs.iplantcollaborative.org/TNRSapp.html')

    def on_tick_off_view_row_activated(self, view, path, column, data=None):
        if self.tick_off_list[path][ACCEPTABLE]:
            to_process = not self.tick_off_list[path][TO_PROCESS]
            self.tick_off_list[path][TO_PROCESS] = to_process
            stock_id = to_process and YES_ICON or NO_ICON
            self.tick_off_list[path][STOCK_ID] = stock_id

    def on_toggle_all_clicked(self, *args):
        all_active = reduce(lambda a, b: a and b,
                            [row[TO_PROCESS] for row in self.tick_off_list
                             if row[ACCEPTABLE]])
        to_process = not all_active
        for row in self.tick_off_list:
            if not row[ACCEPTABLE]:
                continue
            row[TO_PROCESS] = to_process
            stock_id = to_process and YES_ICON or NO_ICON
            row[STOCK_ID] = stock_id


class TaxonomyCheckTool(pluginmgr.Tool):
    label = _('Taxonomy check')

    @classmethod
    def start(self):
        start_taxonomy_check()
