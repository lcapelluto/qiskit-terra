# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
# pylint: disable=invalid-name

"""A module for monitoring backends."""
import warnings

import types
import math
import datetime
from IPython.display import display                     # pylint: disable=import-error
import matplotlib.pyplot as plt                         # pylint: disable=import-error
from matplotlib.patches import Circle                   # pylint: disable=import-error
import ipywidgets as widgets                            # pylint: disable=import-error
from qiskit.exceptions import QiskitError
from qiskit.visualization.gate_map import plot_gate_map, plot_error_map
from qiskit.test.mock import FakeBackend

try:
    # pylint: disable=import-error
    from qiskit.providers.ibmq import IBMQBackend
except ImportError:
    pass

MONTH_NAMES = {1: 'Jan.',
               2: 'Feb.',
               3: 'Mar.',
               4: 'Apr.',
               5: 'May',
               6: 'June',
               7: 'July',
               8: 'Aug.',
               9: 'Sept.',
               10: 'Oct.',
               11: 'Nov.',
               12: 'Dec.'
               }


def _load_jobs_data(self, change):
    """Loads backend jobs data
    """
    if change['new'] == 4 and not self._did_jobs:
        self._did_jobs = True
        year = widgets.Output(layout=widgets.Layout(display='flex-inline',
                                                    align_items='center',
                                                    min_height='400px'))

        month = widgets.Output(layout=widgets.Layout(display='flex-inline',
                                                     align_items='center',
                                                     min_height='400px'))

        week = widgets.Output(layout=widgets.Layout(display='flex-inline',
                                                    align_items='center',
                                                    min_height='400px'))

        self.children[4].children = [year, month, week]
        self.children[4].set_title(0, 'Year')
        self.children[4].set_title(1, 'Month')
        self.children[4].set_title(2, 'Week')
        self.children[4].selected_index = 1
        _build_job_history(self.children[4], self._backend)


def _backend_monitor(backend):
    """ A private function to generate a monitor widget
    for a IBMQ bakend repr.

    Args:
        backend (IBMQBackend | FakeBackend): The backend.

    Raises:
        QiskitError: Input is not an IBMQBackend
    """
    if not isinstance(backend, IBMQBackend) and not isinstance(backend, FakeBackend):
        raise QiskitError('Input variable is not of type IBMQBackend.')
    title_style = "style='color:#ffffff;background-color:#000000;padding-top: 1%;"
    title_style += "padding-bottom: 1%;padding-left: 1%; margin-top: 0px'"
    title_html = "<h1 {style}>{name}</h1>".format(
        style=title_style, name=backend.name())

    details = [config_tab(backend)]

    tab_contents = ['Configuration']

    # Empty jobs tab widget
    jobs = widgets.Tab(layout=widgets.Layout(max_height='620px'))

    if not backend.configuration().simulator:
        tab_contents.extend(['Qubit Properties', 'Multi-Qubit Gates',
                             'Error Map', 'Job History'])

        details.extend([qubits_tab(backend), gates_tab(backend),
                        detailed_map(backend), jobs])

    tabs = widgets.Tab(layout=widgets.Layout(overflow_y='scroll'))
    tabs.children = details
    for i in range(len(details)):
        tabs.set_title(i, tab_contents[i])

    # Make backend accesible to tabs widget
    tabs._backend = backend  # pylint: disable=attribute-defined-outside-init
    tabs._did_jobs = False
    # pylint: disable=attribute-defined-outside-init
    tabs._update = types.MethodType(_load_jobs_data, tabs)

    tabs.observe(tabs._update, names='selected_index')

    title_widget = widgets.HTML(value=title_html,
                                layout=widgets.Layout(margin='0px 0px 0px 0px'))

    bmonitor = widgets.VBox([title_widget, tabs],
                            layout=widgets.Layout(border='4px solid #000000',
                                                  max_height='650px', min_height='650px',
                                                  overflow_y='hidden'))
    display(bmonitor)


def config_tab(backend):
    """The backend configuration widget.

    Args:
        backend (IBMQBackend | FakeBackend): The backend.

    Returns:
        grid: A GridBox widget.
    """
    status = backend.status().to_dict()
    # TODO: remove filters when dt warnings are removed
    warnings.filterwarnings("ignore")
    config = backend.configuration().to_dict()
    warnings.resetwarnings()

    config_dict = {**status, **config}

    upper_list = ['n_qubits']

    if 'quantum_volume' in config.keys():
        if config['quantum_volume']:
            upper_list.append('quantum_volume')

    upper_list.extend(['operational',
                       'status_msg', 'pending_jobs',
                       'backend_version', 'basis_gates',
                       'max_shots', 'max_experiments'])

    lower_list = list(set(config_dict.keys()).difference(upper_list))
    # Remove gates because they are in a different tab
    lower_list.remove('gates')
    # Look for hamiltonian
    if 'hamiltonian' in lower_list:
        htex = config_dict['hamiltonian']['h_latex']
        config_dict['hamiltonian'] = "$$%s$$" % htex

    # Can also be removed when dt warnings are removed
    lower_list.remove('_dt')
    lower_list.remove('_dtm')

    config_dict['dt'] = "{} s".format(config_dict['dt'])
    config_dict['dtm'] = "{} s".format(config_dict['dtm'])

    upper_str = "<table>"
    upper_str += """<style>
table {
    border-collapse: collapse;
    width: auto;
}

th, td {
    text-align: left;
    padding: 8px;
}

tr:nth-child(even) {background-color: #f6f6f6;}
</style>"""

    footer = "</table>"

    # Upper HBox widget data

    upper_str += "<tr><th>Property</th><th>Value</th></tr>"
    for key in upper_list:
        upper_str += "<tr><td><font style='font-weight:bold'>%s</font></td><td>%s</td></tr>" % (
            key, config_dict[key])
    upper_str += footer

    upper_table = widgets.HTMLMath(
        value=upper_str, layout=widgets.Layout(width='100%', grid_area='left'))

    image_widget = widgets.Output(
        layout=widgets.Layout(display='flex-inline', grid_area='right',
                              padding='10px 10px 10px 10px',
                              width='auto', max_height='325px',
                              align_items='center'))

    if not config['simulator']:
        with image_widget:
            gate_map = plot_gate_map(backend)
            display(gate_map)
        plt.close(gate_map)

    lower_str = "<table>"
    lower_str += """<style>
table {
    border-collapse: collapse;
    width: auto;
}

th, td {
    text-align: left;
    padding: 8px;
}

tr:nth-child(even) {background-color: #f6f6f6;}
</style>"""
    lower_str += "<tr><th></th><th></th></tr>"
    for key in lower_list:
        if key != 'name':
            lower_str += "<tr><td>%s</td><td>%s</td></tr>" % (
                key, config_dict[key])
    lower_str += footer

    lower_table = widgets.HTMLMath(value=lower_str,
                                   layout=widgets.Layout(
                                       width='auto',
                                       grid_area='bottom'))

    grid = widgets.GridBox(children=[upper_table, image_widget, lower_table],
                           layout=widgets.Layout(
                               grid_template_rows='auto auto',
                               grid_template_columns='31% 23% 23% 23%',
                               grid_template_areas='''
                               "left right right right"
                               "bottom bottom bottom bottom"
                               ''',
                               grid_gap='0px 0px'))

    return grid


def qubits_tab(backend):
    """The qubits properties widget

    Args:
        backend (IBMQBackend | FakeBackend): The backend.

    Returns:
        VBox: A VBox widget.
    """
    props = backend.properties().to_dict()

    header_html = "<div><font style='font-weight:bold'>{key}</font>: {value}</div>"
    header_html = header_html.format(key='last_update_date',
                                     value=props['last_update_date'])
    update_date_widget = widgets.HTML(value=header_html)

    qubit_html = "<table>"
    qubit_html += """<style>
table {
    border-collapse: collapse;
    width: auto;
}

th, td {
    text-align: left;
    padding: 8px;
}

tr:nth-child(even) {background-color: #f6f6f6;}
</style>"""

    qubit_html += "<tr><th></th><th>Frequency</th><th>T1</th><th>T2</th>"
    qubit_html += "<th>U1 gate error</th><th>U2 gate error</th><th>U3 gate error</th>"
    qubit_html += "<th>Readout error</th></tr>"
    qubit_footer = "</table>"

    for qub in range(len(props['qubits'])):
        name = 'Q%s' % qub
        qubit_data = props['qubits'][qub]
        gate_data = [g for g in props['gates'] if g['qubits'] == [qub]]
        t1_info = qubit_data[0]
        t2_info = qubit_data[1]
        freq_info = qubit_data[2]
        readout_info = qubit_data[3]

        freq = str(round(freq_info['value'], 5))+' '+freq_info['unit']
        T1 = str(round(t1_info['value'],
                       5))+' ' + t1_info['unit']
        T2 = str(round(t2_info['value'],
                       5))+' ' + t2_info['unit']

        for gd in gate_data:
            if gd['gate'] == 'u1':
                U1 = str(round(gd['parameters'][0]['value'], 5))
                break

        for gd in gate_data:
            if gd['gate'] == 'u2':
                U2 = str(round(gd['parameters'][0]['value'], 5))
                break
        for gd in gate_data:
            if gd['gate'] == 'u3':
                U3 = str(round(gd['parameters'][0]['value'], 5))
                break

        readout_error = round(readout_info['value'], 5)
        qubit_html += "<tr><td><font style='font-weight:bold'>%s</font></td><td>%s</td>"
        qubit_html += "<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        qubit_html = qubit_html % (name, freq, T1, T2, U1, U2, U3, readout_error)
    qubit_html += qubit_footer

    qubit_widget = widgets.HTML(value=qubit_html)

    out = widgets.VBox([update_date_widget,
                        qubit_widget])

    return out


def gates_tab(backend):
    """The multiple qubit gate error widget.

    Args:
        backend (IBMQBackend | FakeBackend): The backend.

    Returns:
        VBox: A VBox widget.
    """
    props = backend.properties().to_dict()

    multi_qubit_gates = [g for g in props['gates'] if len(g['qubits']) > 1]

    header_html = "<div><font style='font-weight:bold'>{key}</font>: {value}</div>"
    header_html = header_html.format(key='last_update_date',
                                     value=props['last_update_date'])

    update_date_widget = widgets.HTML(value=header_html,
                                      layout=widgets.Layout(grid_area='top'))

    gate_html = "<table>"
    gate_html += """<style>
table {
    border-collapse: collapse;
    width: auto;
}

th, td {
    text-align: left;
    padding: 8px;
}

tr:nth-child(even) {background-color: #f6f6f6;};
</style>"""

    gate_html += "<tr><th></th><th>Type</th><th>Gate error</th></tr>"
    gate_footer = "</table>"

    # Split gates into two columns
    left_num = math.ceil(len(multi_qubit_gates)/3)
    mid_num = math.ceil((len(multi_qubit_gates)-left_num)/2)

    left_table = gate_html

    for qub in range(left_num):
        gate = multi_qubit_gates[qub]
        qubits = gate['qubits']
        ttype = gate['gate']
        error = round(gate['parameters'][0]['value'], 5)

        left_table += "<tr><td><font style='font-weight:bold'>%s</font>"
        left_table += "</td><td>%s</td><td>%s</td></tr>"
        left_table = left_table % ("{}{}_{}".format(ttype, qubits[0], qubits[1]),
                                   ttype, error)
    left_table += gate_footer

    middle_table = gate_html

    for qub in range(left_num, left_num+mid_num):
        gate = multi_qubit_gates[qub]
        qubits = gate['qubits']
        ttype = gate['gate']
        error = round(gate['parameters'][0]['value'], 5)

        middle_table += "<tr><td><font style='font-weight:bold'>%s</font>"
        middle_table += "</td><td>%s</td><td>%s</td></tr>"
        middle_table = middle_table % ("{}{}_{}".format(ttype, qubits[0], qubits[1]),
                                       ttype, error)
    middle_table += gate_footer

    right_table = gate_html

    for qub in range(left_num+mid_num, len(multi_qubit_gates)):
        gate = multi_qubit_gates[qub]
        qubits = gate['qubits']
        ttype = gate['gate']
        error = round(gate['parameters'][0]['value'], 5)

        right_table += "<tr><td><font style='font-weight:bold'>%s</font>"
        right_table += "</td><td>%s</td><td>%s</td></tr>"
        right_table = right_table % ("{}{}_{}".format(ttype, qubits[0], qubits[1]),
                                     ttype, error)
    right_table += gate_footer

    left_table_widget = widgets.HTML(value=left_table,
                                     layout=widgets.Layout(grid_area='left'))
    middle_table_widget = widgets.HTML(value=middle_table,
                                       layout=widgets.Layout(grid_area='middle'))
    right_table_widget = widgets.HTML(value=right_table,
                                      layout=widgets.Layout(grid_area='right'))

    grid = widgets.GridBox(children=[update_date_widget,
                                     left_table_widget,
                                     middle_table_widget,
                                     right_table_widget],
                           layout=widgets.Layout(
                               grid_template_rows='auto auto',
                               grid_template_columns='33% 33% 33%',
                               grid_template_areas='''
                                                   "top top top"
                                                   "left middle right"
                                                   ''',
                               grid_gap='0px 0px'))

    return grid


def detailed_map(backend):
    """Widget for displaying detailed noise map.

    Args:
        backend (IBMQBackend | FakeBackend): The backend.

    Returns:
        GridBox: Widget holding noise map images.
    """
    error_widget = widgets.Output(layout=widgets.Layout(display='flex-inline',
                                                        align_items='center'))
    with error_widget:
        display(plot_error_map(backend, figsize=(11, 9), show_title=False))
    return error_widget


def job_history(backend):
    """Widget for displaying job history

    Args:
     backend (IBMQBackend | FakeBackend): The backend.

    Returns:
        Tab: A tab widget for history images.
    """
    year = widgets.Output(layout=widgets.Layout(display='flex-inline',
                                                align_items='center',
                                                min_height='400px'))

    month = widgets.Output(layout=widgets.Layout(display='flex-inline',
                                                 align_items='center',
                                                 min_height='400px'))

    week = widgets.Output(layout=widgets.Layout(display='flex-inline',
                                                align_items='center',
                                                min_height='400px'))

    tabs = widgets.Tab(layout=widgets.Layout(max_height='620px'))
    tabs.children = [year, month, week]
    tabs.set_title(0, 'Year')
    tabs.set_title(1, 'Month')
    tabs.set_title(2, 'Week')
    tabs.selected_index = 1

    _build_job_history(tabs, backend)
    return tabs


def _build_job_history(tabs, backend):

    past_year_date = datetime.datetime.now() - datetime.timedelta(days=365)
    date_filter = {'creationDate': {'gt': past_year_date.isoformat()}}
    jobs = backend.jobs(limit=None, db_filter=date_filter)

    with tabs.children[0]:
        year_plot = plot_job_history(jobs, interval='year')
        display(year_plot)
        plt.close(year_plot)

    with tabs.children[1]:
        month_plot = plot_job_history(jobs, interval='month')
        display(month_plot)
        plt.close(month_plot)

    with tabs.children[2]:
        week_plot = plot_job_history(jobs, interval='week')
        display(week_plot)
        plt.close(week_plot)


def plot_job_history(jobs, interval='year'):
    """Plots the job history of the user from the given list of jobs.

    Args:
        jobs (list): A list of jobs with type IBMQjob.
        interval (str): Interval over which to examine.

    Returns:
        fig: A Matplotlib figure instance.
    """
    def get_date(job):
        """Returns a datetime object from a IBMQJob instance.

        Args:
            job (IBMQJob): A job.

        Returns:
            dt: A datetime object.
        """
        return datetime.datetime.strptime(job.creation_date(),
                                          '%Y-%m-%dT%H:%M:%S.%fZ')

    current_time = datetime.datetime.now()

    if interval == 'year':
        bins = [(current_time - datetime.timedelta(days=k*365/12))
                for k in range(12)]
    elif interval == 'month':
        bins = [(current_time - datetime.timedelta(days=k)) for k in range(30)]
    elif interval == 'week':
        bins = [(current_time - datetime.timedelta(days=k)) for k in range(7)]

    binned_jobs = [0]*len(bins)

    if interval == 'year':
        for job in jobs:
            for ind, dat in enumerate(bins):
                date = get_date(job)
                if date.month == dat.month:
                    binned_jobs[ind] += 1
                    break
            else:
                continue
    else:
        for job in jobs:
            for ind, dat in enumerate(bins):
                date = get_date(job)
                if date.day == dat.day and date.month == dat.month:
                    binned_jobs[ind] += 1
                    break
            else:
                continue

    nz_bins = []
    nz_idx = []
    for ind, val in enumerate(binned_jobs):
        if val != 0:
            nz_idx.append(ind)
            nz_bins.append(val)

    total_jobs = sum(binned_jobs)

    colors = ['#003f5c', '#ffa600', '#374c80', '#ff764a',
              '#7a5195', '#ef5675', '#bc5090']

    if interval == 'year':
        labels = ['{}-{}'.format(str(bins[b].year)[2:], MONTH_NAMES[bins[b].month]) for b in nz_idx]
    else:
        labels = ['{}-{}'.format(MONTH_NAMES[bins[b].month], bins[b].day) for b in nz_idx]
    fig, ax = plt.subplots(1, 1, figsize=(5.5, 5.5))  # pylint: disable=invalid-name
    ax.pie(nz_bins[::-1], labels=labels, colors=colors, textprops={'fontsize': 14},
           rotatelabels=True, counterclock=False, radius=1)
    ax.add_artist(Circle((0, 0), 0.7, color='white', zorder=1))
    ax.text(0, 0, total_jobs, horizontalalignment='center',
            verticalalignment='center', fontsize=26)
    return fig
