# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import json

from app.home import blueprint
from flask import render_template, redirect, url_for, request
from flask_login import login_required, current_user
from app import login_manager
from jinja2 import TemplateNotFound

from app.models.activity import (
    CongressBill,
    CongressBillAction,
    CongressVote,
    LobbyDisclosure1,
    LobbyDisclosure2,
    LobbyDisclosure203,
    ScheduleA,
    ScheduleB
)

MODEL_CLASSES = [
#    CongressBill,
#    CongressBillAction,
    CongressVote,
#    LobbyDisclosure1,
#    LobbyDisclosure2,
    LobbyDisclosure203,
#    ScheduleA,
    ScheduleB
]

@blueprint.route('/index')
def index():
    all_results = []
    mapped_results = {MC.activity_type: [] for MC in MODEL_CLASSES}
    search_models = set()

    data_types = request.args.get("types", "all")
    data_types = data_types.split(",")

    search_models = [
        MC
        for MC in MODEL_CLASSES
        if (MC.activity_type in data_types) or ("all" in data_types)
    ]

    query = request.args.get("gquery")
    if query is not None:
        for MC in search_models:
            search_query = f"%{query}%"
            results = MC.query.filter(MC.tags.like(search_query)).all()

            results = sorted(results, key=lambda x: x.date, reverse=True)
            mapped_results[MC.activity_type] = results

            all_results.extend(results)

    mapped_results["all"] = all_results

    start = request.args.get("start", 0)
    if str(start).isdigit():
        start = max(0, int(start))
    else:
        start = 0

    n_per_page = request.args.get("npp", 10)
    if str(n_per_page).isdigit():
        n_per_page = max(1, int(n_per_page))
    else:
        n_per_page = 10

    display_table_type = request.args.get("dsp_type", data_types[0])

    return render_template('index.html',
                            segment='index',
                            mapped_results=mapped_results,
                            query=query,
                            start=start,
                            n_per_page=n_per_page,
                            display_table_type=display_table_type)


@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith( '.html' ):
            template += '.html'

        # Detect the current page
        segment = get_segment( request )

        # Serve the file (if exists) from app/templates/FILE.html
        return render_template( template, segment=segment )

    except TemplateNotFound:
        return render_template('page-404.html'), 404

    except:
        return render_template('page-500.html'), 500

# Helper - Extract current page name from request
def get_segment( request ):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'index'

        return segment

    except:
        return None
