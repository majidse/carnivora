import json
import operator
import os
import pickle
import subprocess

from django.contrib.auth import logout, authenticate, login
from django.shortcuts import render, render_to_response
from django.utils.datastructures import MultiValueDictKeyError
from django.contrib.auth.models import User

from carnivora.instabot.config import ConfigLoader, Config
from carnivora.instabot.driver import Driver
from carnivora.instabot.log import Log
from carnivora.instabot.statistics import Statistics
from tf_open_nsfw.classify_nsfw import classify_nsfw

from django.contrib.auth.decorators import user_passes_test

page_size = 20


def index(request):
    return render_to_response('index.html')


def main_body(request):
    if request.user.is_authenticated:
        return render(request, 'main-body.html')
    else:
        return render(request, 'login.html')


def login_user(request):
    logout(request)
    username = request.GET['username']
    password = request.GET['password']

    user = authenticate(username=username, password=password)
    if user is not None:
        if user.is_active:
            login(request, user=user)
            return render(request, 'main-body.html')
    return render(request, 'login.html', {'message': 'Login failed. Please try again.'})


def load_registration(request):
    username = request.GET['username']
    password = request.GET['password']
    return render(request, 'register.html', {'username': username, 'password': password})


def register_user(request):
    logout(request)
    username = request.GET['username']
    email = request.GET['email']
    password = request.GET['password']

    User.objects.create_user(username=username, email=email, password=password)

    user = authenticate(username=username, password=password)
    if user is not None:
        if user.is_active:
            login(request, user=user)
            return render(request, 'main-body.html')
    return render(request, 'register.html', {'message': 'Registration failed. Please try again.'})


def load_button_chain(request):
    if not request.user.is_authenticated:
        return
    username = request.user.username
    log_path = Config.bot_path + "/log/" + username
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    running_path = log_path + "/running.pickle"
    try:
        with open(running_path, "rb") as f:
            active = bool(pickle.load(f))
    except:
        active = False
    return render(request, 'buttonchain.html', {'active': active})


def run_instabot(request):
    if not request.user.is_authenticated:
        return

    username = request.GET['username']
    password = request.GET['password']

    log_path = Config.bot_path + "/log/" + username
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    running_path = log_path + "/running.pickle"
    with open(running_path, "wb") as f:
        pickle.dump(True, f)

    driver = Driver(username=username, password=password)
    driver.start()
    return render(request, 'buttonchain.html', {'active': True})


def stop_instabot(request):
    if not request.user.is_authenticated:
        return
    username = request.user.username
    log_path = Config.bot_path + "/log/" + username
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    running_path = log_path + "/running.pickle"
    with open(running_path, "wb") as f:
        pickle.dump(False, f)
    return render(request, 'buttonchain.html', {'active': False})


@user_passes_test(lambda u: u.is_superuser)
def update_server(request):
    commands = [["git", "status"], ["git", "pull"]]
    output = []
    for command in commands:
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        output.append(
            (" ".join(command), process.stdout, str(process.wait(timeout=30)))
        )
    return render(request, 'server_update.html', {'output': output})


def table_monitor_update(request):
    if not request.user.is_authenticated:
        return
    # pages = range(Log.number_of_pages(page_size=page_size))
    try:
        search = request.GET['search']
    except MultiValueDictKeyError as e:
        print(e)
        search = ''
    username = request.user.username
    log_path = Config.bot_path + "/log/" + username
    path = log_path + "/log.pickle"
    lines = Log.get(logpath=path, page_size=page_size, search=search)
    return render(request, 'table_monitor_update.html', {'lines': lines})


@user_passes_test(lambda u: u.is_superuser)
def submit_to_config(request):
    try:
        config_key = request.GET['config_key']
        config_param = request.GET['config_param']
        ConfigLoader.store(config_key, config_param)
        return render(request, 'settings_update.html', {'config_key': config_key, 'config_param': config_param})
    except MultiValueDictKeyError as e:
        print(e)
        return render(request, 'settings_update.html')


def monitor(request):
    if not request.user.is_authenticated:
        return
    # pages = range(Log.number_of_pages(page_size=page_size))
    username = request.user.username
    log_path = Config.bot_path + "/log/" + username
    path = log_path + "/log.pickle"
    lines = Log.get(logpath=path, page_size=page_size)
    return render(request, 'monitor.html', {'lines': lines})


def statistics(request):
    if not request.user.is_authenticated:
        return
    username = request.user.username
    hashtag_names, hashtag_scores = Statistics.get_hashtags(username=username, n=40, truncated_name_length=20)
    amount_of_users, amount_of_interactions, amount_of_likes, amount_of_follows, amount_of_comments \
        = Statistics.get_amount_of_actions(username=username)
    amount_of_follows_all_time = Statistics.get_amount_of_followed_accounts(username=username)
    render_data = {
        'hashtag_names': json.dumps(hashtag_names),
        'hashtag_scores': hashtag_scores,
        'amount_of_users': amount_of_users,
        'amount_of_likes': amount_of_likes,
        'amount_of_comments': amount_of_comments,
        'amount_of_follows': amount_of_follows,
        'amount_of_interactions': amount_of_interactions,
        'amount_of_follows_all_time': amount_of_follows_all_time,
    }
    return render(request, 'statistics.html', render_data)


@user_passes_test(lambda u: u.is_superuser)
def submit_nsfw(request):
    try:
        link = request.GET['nsfw_link']
        sfw, nsfw = classify_nsfw(link)
        return render(request, 'nsfw_progress_bar.html', {'nsfw': int(nsfw*100)})
    except MultiValueDictKeyError as e:
        print(e)
        return render(request, 'nsfw_progress_bar.html', {'nsfw': 0})


@user_passes_test(lambda u: u.is_superuser)
def server(request):
    return render(request, 'server.html')


@user_passes_test(lambda u: u.is_superuser)
def nsfw_check(request):
    return render(request, 'nsfw_check.html')


@user_passes_test(lambda u: u.is_superuser)
def perform_reboot(request):
    os.system('sudo reboot now')


@user_passes_test(lambda u: u.is_superuser)
def settings(request):
    config = ConfigLoader.load()
    sorted_config = sorted(config.items(), key=operator.itemgetter(0))
    return render(request, 'settings.html', {'sorted_config': sorted_config})
