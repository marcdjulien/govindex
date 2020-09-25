# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import click
from flask import Flask, url_for
from flask_sqlalchemy import SQLAlchemy
from importlib import import_module
from logging import basicConfig, DEBUG, getLogger, StreamHandler
import os
import json
import yaml
from dateutil import parser


db = SQLAlchemy()

# Must be aster db is created.
from app.db_commands import (
    PUBLISH_MAP,
    publish,
    publish_tags,
)


CURRENT_LEGISLATORS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__name__)),
    "app",
    "data",
    "legislators-current.yaml"
)

EXECUTIVE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__name__)),
    "app",
    "data",
    "executive.yaml"
)

govtrack_ids = {}
lis_ids = {}
bioguide_ids = {}
fec_ids = {}
committee_ids = {}
schedule_b_codes = {}

id_maps = {
    "govtrack": govtrack_ids,
    "lis": lis_ids,
    "bioguide": bioguide_ids,
    "fec": fec_ids,
    "committee": committee_ids,
    "schedule_b_codes": schedule_b_codes,
}


def load_memory_data():
    # TODO: Get rid of the globals
    global govtrack_ids
    global lis_ids
    global bioguide_ids
    global fec_ids
    global committee_ids
    global schedule_b_codes

    print("Initializing memory data ...")
    # For now, assuming legislators and executive are mutually exclusive
    with open(CURRENT_LEGISLATORS_PATH, "r") as f1:
        with open(EXECUTIVE_PATH, "r") as f2:
            info = yaml.safe_load(f1) + yaml.safe_load(f2)
            for c in info:
                details = {key: c[key] for key in c}
                if "govtrack" in c["id"]:
                    govtrack_ids[c["id"]["govtrack"]] = details

                if "bioguide" in c["id"]:
                    bioguide_ids[c["id"]["bioguide"]] = details

                if "lis" in c["id"]:
                    lis_ids[c["id"]["lis"]] = details

            for profile in govtrack_ids.values():
                if "official_full" not in profile["name"]:
                    name = []
                    for key in ["first", "middle", "last"]:
                        name.append(profile["name"].get(key, ""))
                    profile["name"]["official_full"] = " ".join(tok for tok in name if tok)

            # Map FEC ID to profile
            for gid in govtrack_ids:
                for fec_id in govtrack_ids[gid]["id"].get("fec", []):
                    fec_ids[fec_id] = govtrack_ids[gid]


    # Parse FEC info
    # For now just 2020
    # TODO: parse all years
    with open("app/data/weball20.txt") as f:
        for line in f:
            data = line.split("|")
            fec_id = data[0]
            name = data[1]
            try:
                last, first = name.split(",", 1)
            except:
                try:
                    last, first = name.split(" ", 1)
                except:
                    full_name = name
                    last = name
                    first = name
            last = last.strip().capitalize()
            first = first.strip().capitalize()
            full_name = f"{first} {last}"

            if fec_id not in fec_ids:
                info = {
                    "id": {"fec":[fec_id]},
                    "name": {
                        "first":first,
                        "last":last,
                        "official_full": full_name
                    }
                }
                fec_ids[fec_id] = info


    # Parse FEC info
    # For now just 2020
    # TODO: parse all years
    with open("app/data/cm20.txt") as f:
        for line in f:
            data = line.split("|")
            fec_id = data[0]
            name = data[1]
            committee_ids[fec_id] = name


    with open("app/data/schedule_b_codes.txt") as f:
        for line in f:
            data = line.split(" ", 1)
            schedule_b_codes[data[0].strip()] = data[1].strip()

def memory_initialization(app):
    @app.before_first_request
    def load():
        load_memory_data()

def register_extensions(app):
    db.init_app(app)

def register_blueprints(app):
    for module_name in ('base', 'home'):
        module = import_module('app.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)

def configure_database(app):

    @app.before_first_request
    def initialize_database():
        db.create_all()

    @app.teardown_request
    def shutdown_session(exception=None):
        db.session.remove()

def register_commands(app):
    @app.cli.command("publish-data")
    @click.argument('type')
    @click.argument('source_dir')
    def publish_data(type, source_dir):
        """Publish data to the database."""
        f = PUBLISH_MAP.get(type)
        if f is None:
            print(f"Invalid type: {type}")
            return
        else:
            load_memory_data()
            f(db, source_dir, id_maps)

    @app.cli.command("publish")
    @click.argument('filename')
    def publish_all(filename):
        """Publish data to the database."""
        load_memory_data()
        publish(db, filename, id_maps)

    @app.cli.command("tag-db")
    def tag_db():
        publish_tags(db)

    @app.cli.command("cust")
    def cust():
        db.engine.execute("DELETE FROM results WHERE results.type == \"ld2\"")
        db.session.commit()

    app.cli.add_command(publish_data)
    app.cli.add_command(publish_all)
    app.cli.add_command(tag_db)
    app.cli.add_command(cust)

def register_filters(app):
    @app.template_filter('date')
    def date(d, fmt):
        return d.strftime(fmt) if d else "No Date"

    @app.template_filter('smart_find')
    def smart_find(id):
        for collection in [bioguide_ids, lis_ids, fec_ids, govtrack_ids]:
            if id in collection:
                return collection[id]["name"]["official_full"]
        return id

    @app.template_filter('bioguide_to_name')
    def bioguide_to_name(id):
        return bioguide_ids[id]["name"]["official_full"]

    @app.template_filter('fec_to_name')
    def fec_to_name(id):
        return fec_ids[id]["name"]["official_full"]

    @app.template_filter('committee_id_to_name')
    def committee_id_to_name(id):
        return committee_ids[id]

    @app.template_filter('schdb_code')
    def schdb_code(code):
        return schedule_b_codes.get(code)

    @app.template_filter('qurl')
    def query_url(query):
        return f"/index?gquery={query}"

    @app.template_filter('govtrack_bill_url')
    def govtrack_bill_url(bill_id):
        try:
            congress, bill = bill_id.split("-")
            return f"https://www.govtrack.us/congress/bills/{bill}/{congress}"
        except:
            return f"https://www.govtrack.us/search?q={bill_id}"

    @app.template_filter('govtrack_cand_url')
    def govtrack_cand_url(id):
        if id in bioguide_ids:
            id = bioguide_ids[id]["id"]["govtrack"]
        elif id in lis_ids:
            id = lis_ids[id]["id"]["govtrack"]
        else:
            return f"index/q={id}"
        return f"https://www.govtrack.us/congress/members/{id}"

    @app.template_filter('next_page')
    def next_page(params, n):
        new_params = params.copy()
        start = int(params["start"]) if "start" in params else 0
        n_per_page = int(params["npp"]) if "npp" in params else 100
        new_params["start"] = start + n_per_page
        return new_params

    @app.template_filter('prev_page')
    def prev_page(params, n):
        new_params = params.copy()
        start = int(params["start"]) if "start" in params else 0
        n_per_page = int(params["npp"]) if "npp" in params else 100
        new_params["start"] = max(0, start - n_per_page)
        return new_params

    @app.template_filter('show_all')
    def show_all(params, n):
        new_params = params.copy()
        start = int(params["start"]) if "start" in params else 0
        n_per_page = int(params["npp"]) if "npp" in params else 100
        new_params["start"] = 0
        new_params["npp"] = n
        return new_params

    @app.template_filter('new_dsp_type')
    def new_dsp_type(params, type):
        new_params = params.copy()
        new_params["dsp_type"] = type
        if "start" in params:
            del new_params["start"]
        if "npp" in params:
            del new_params["npp"]
        return new_params


    @app.template_filter('vote_color')
    def vote_color(vote_status):
        mapping = {
            "cv-no": ["no", "nay"],
            "cv-yes": ["yes", "aye", "yea"],
            "cv-nv":["not voting"]
        }
        for theme, status in mapping.items():
            if vote_status.lower() in status:
                return theme
        return "cv-nv"

    @app.template_filter('result_url')
    def result_url(result):
        return "index?gquery={}".format(
            result["tags"].replace(",", "+"))

    @app.template_filter('activity_type_html')
    def activity_type_html(activity_type):
        mapping = {
            "congress_vote": "includes/cards/congress_vote.html",
            "schedule_b": "includes/cards/schedule_b.html",
            "ld1": "includes/cards/ld1.html",
            "ld2": "includes/cards/ld2.html",
            "ld203": "includes/cards/ld203.html",
        }
        return mapping.get(activity_type, "includes/cards/none.html")

def create_app(config):
    app = Flask(__name__, static_folder='base/static')
    app.config.from_object(config)
    register_extensions(app)
    register_blueprints(app)
    register_commands(app)
    register_filters(app)
    configure_database(app)
    memory_initialization(app)

    return app