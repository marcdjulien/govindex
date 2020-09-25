# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import json
import re
from collections import defaultdict

from app import db
from app.home import blueprint
from flask import render_template, redirect, url_for, request
from jinja2 import TemplateNotFound
from sqlalchemy import func, or_

from app.models.activity import Result, Tag
import orjson

@blueprint.route('/')
@blueprint.route('/index')
def index():
    mapped_results = defaultdict(list)
    query = request.args.get("gquery")
    if query is not None:
        print(f"QUERY: {query}")
        keywords = []

        attrs = []
        special_search_groups = re.search(r'(".+": ".+")', query)
        if special_search_groups:
            attrs.extend(special_search_groups.groups())
            for ssg in special_search_groups.groups():
                query = query.replace(ssg, "")

        grouped = re.search(r"\"(.+)\"", query)
        if grouped:
            keywords.extend(grouped.groups())
            for g in grouped.groups():
                query = query.replace(g, "")
            query = query.replace("\"", "")

        keywords.extend([q for q in query.split() if q])

        print(f"KEYWORDS: {keywords}")
        q = Result.query
        for kw in keywords:
            q = q.filter(Result.tags.like(f"%{kw}%"))

        print(f"ATTRS: {attrs}")
        for a in attrs:
            q = q.filter(Result.details.like(f"%{a}%"))

        q = q.order_by(Result.date.desc())
        results = q.all()

        for r in results:
            details = orjson.loads(r.details)
            details["id"] = r.id
            details["source"] = r.source
            details["date"] = r.date
            details["activity_type"] = r.type
            details["last_updated"] = r.last_updated
            details["source"] = r.source
            details["tags"] = r.tags
            mapped_results[r.type].append(details)
            mapped_results["all"].append(details)

    start = request.args.get("start", 0)
    if str(start).isdigit():
        start = max(0, int(start))
    else:
        start = 0

    n_per_page = request.args.get("npp", 100)
    if str(n_per_page).isdigit():
        n_per_page = max(1, int(n_per_page))
    else:
        n_per_page = 10

    data_type = request.args.get("types", "all")
    display_table_type = request.args.get("dsp_type", data_type)

    return render_template('index.html',
                            segment='index',
                            mapped_results=mapped_results,
                            query=request.args.get("gquery"),
                            start=start,
                            n_per_page=n_per_page,
                            display_table_type=display_table_type)

@blueprint.route('/result')
def result():
    id = request.args.get("id")
    if id is not None:
        result = Result.query.filter(Result.id==id).first_or_404()
        details = orjson.loads(result.details)
        details["id"] = result.id
        details["source"] = result.source
        details["date"] = result.date
        details["activity_type"] = result.type
        details["last_updated"] = result.last_updated
        details["source"] = result.source
        details["tags"] = result.tags
        return render_template('result.html',
                               segment='index',
                               result=details)


@blueprint.route('/<template>')
def route_template(template):
    try:
        if not template.endswith('.html'):
            template += '.html'
        # Detect the current page
        segment = get_segment( request )
        # Serve the file (if exists) from app/templates/FILE.html
        return render_template(template, segment=segment)
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
