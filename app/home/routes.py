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

@blueprint.route('/index/<query>')
#@login_required
def index(query):
    results = []
    for ModelClass in (
        CongressBill,
        CongressBillAction,
        CongressVote,
        LobbyDisclosure1,
        LobbyDisclosure2,
        LobbyDisclosure203,
        ScheduleA,
        ScheduleB
    ):
        search_query = f"%{query}%"
        results.extend(ModelClass.query.filter(ModelClass.tags.like(search_query)).all())

    results = sorted(results, key=lambda x: x.date, reverse=True)

    return render_template('index.html',
                            segment='index',
                            results=results,
                            n=len(results))


@blueprint.route('/<template>')
#@login_required
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
