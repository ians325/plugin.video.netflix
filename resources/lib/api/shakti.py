# -*- coding: utf-8 -*-
"""Access to Netflix's Shakti API"""
from __future__ import unicode_literals

import json

import resources.lib.common as common
import resources.lib.cache as cache
from resources.lib.services.nfsession import NetflixSession

from .data_types import LoLoMo, VideoList, SeasonList, EpisodeList
from .paths import (VIDEO_LIST_PARTIAL_PATHS, SEASONS_PARTIAL_PATHS,
                    EPISODES_PARTIAL_PATHS, ART_PARTIAL_PATHS)

class InvalidVideoListTypeError(Exception):
    """No video list of a given was available"""
    pass

def activate_profile(profile_id):
    """Activate the profile with the given ID"""
    cache.invalidate_cache()
    common.make_call(NetflixSession.activate_profile, profile_id)

def logout():
    """Logout of the current account"""
    cache.invalidate_cache()
    common.make_call(NetflixSession.logout)

def login():
    """Perform a login"""
    cache.invalidate_cache()
    common.make_call(NetflixSession.login)

def profiles():
    """Retrieve the list of available user profiles"""
    return common.make_call(NetflixSession.list_profiles)

@cache.cache_output(cache.CACHE_COMMON, fixed_identifier='root_lists')
def root_lists():
    """Retrieve initial video lists to display on homepage"""
    common.debug('Requesting root lists from API')
    return LoLoMo(common.make_call(
        NetflixSession.path_request,
        [['lolomo',
          {'from': 0, 'to': 40},
          ['displayName', 'context', 'id', 'index', 'length']]]))

@cache.cache_output(cache.CACHE_COMMON, 0, 'list_type')
def list_id_for_type(list_type):
    """Return the dynamic video list ID for a video list of known type"""
    try:
        list_id = next(root_lists().lists_by_context(list_type))[0]
    except StopIteration:
        raise InvalidVideoListTypeError(
            'No lists of type {} available'.format(list_type))
    common.debug(
        'Resolved list ID for {} to {}'.format(list_type, list_id))
    return list_id

@cache.cache_output(cache.CACHE_VIDEO_LIST, 0, 'list_id')
def video_list(list_id):
    """Retrieve a single video list"""
    common.debug('Requesting video list {}'.format(list_id))
    return VideoList(common.make_call(
        NetflixSession.path_request,
        build_paths(['lists', [list_id], {'from': 0, 'to': 40}, 'reference'],
                    VIDEO_LIST_PARTIAL_PATHS)))

@cache.cache_output(cache.CACHE_SEASONS, 0, 'tvshow_id')
def seasons(tvshow_id):
    """Retrieve seasons of a TV show"""
    common.debug('Requesting season list for show {}'.format(tvshow_id))
    return SeasonList(
        tvshow_id,
        common.make_call(
            NetflixSession.path_request,
            build_paths(['videos', tvshow_id],
                        SEASONS_PARTIAL_PATHS)))

@cache.cache_output(cache.CACHE_EPISODES, 1, 'season_id')
def episodes(tvshow_id, season_id):
    """Retrieve episodes of a season"""
    common.debug('Requesting episode list for show {}, season {}'
                 .format(tvshow_id, season_id))
    return EpisodeList(
        tvshow_id,
        season_id,
        common.make_call(
            NetflixSession.path_request,
            build_paths(['seasons', season_id, 'episodes',
                         {'from': 0, 'to': 40}],
                        EPISODES_PARTIAL_PATHS) +
            build_paths(['videos', tvshow_id],
                        ART_PARTIAL_PATHS +
                        [['title']])))

@cache.cache_output(cache.CACHE_EPISODES, 1, 'episode_id')
def episode(tvshow_id, episode_id):
    """Retrieve info for a single episode"""
    common.debug('Requesting single episode info for {}'
                 .format(episode_id))
    return common.make_call(
        NetflixSession.path_request,
        build_paths(['videos', episode_id],
                    EPISODES_PARTIAL_PATHS) +
        build_paths(['videos', tvshow_id],
                    ART_PARTIAL_PATHS +
                    [['title']]))

@cache.cache_output(cache.CACHE_EPISODES, 0, 'movie_id')
def movie(movie_id):
    """Retrieve info for a single movie"""
    common.debug('Requesting movie info for {}'
                 .format(movie_id))
    return common.make_call(
        NetflixSession.path_request,
        build_paths(['videos', movie_id],
                    EPISODES_PARTIAL_PATHS))

def rate(video_id, rating):
    """Rate a video on Netflix"""
    common.debug('Rating {} as {}'.format(video_id, rating))
    # In opposition to Kodi, Netflix uses a rating from 0 to in 0.5 steps
    rating = min(10, max(0, rating)) / 2
    common.make_call(
        NetflixSession.post,
        {'component': 'set_video_rating',
         'headers': {
             'Content-Type': 'application/json',
             'Accept': 'application/json, text/javascript, */*'},
         'params': {
             'titleid': video_id,
             'rating': rating}})

def add_to_list(video_id):
    """Add a video to my list"""
    common.debug('Adding {} to my list'.format(video_id))
    _update_my_list(video_id, 'add')

def remove_from_list(video_id):
    """Remove a video from my list"""
    common.debug('Removing {} from my list'.format(video_id))
    _update_my_list(video_id, 'remove')

def _update_my_list(video_id, operation):
    """Call API to update my list with either add or remove action"""
    common.make_call(
        NetflixSession.post,
        {'component': 'update_my_list',
         'headers': {
             'Content-Type': 'application/json',
             'Accept': 'application/json, text/javascript, */*'},
         'data': {
             'operation': operation,
             'videoId': int(video_id)}})
    if common.ADDON.getSettingBool('invalidate_cache_on_mylist_modify'):
        cache.invalidate_cache()
    else:
        cache.invalidate_last_location()
        cache.invalidate_entry(cache.CACHE_VIDEO_LIST,
                               list_id_for_type('queue'))
        cache.invalidate_entry(cache.CACHE_COMMON, 'queue')
        cache.invalidate_entry(cache.CACHE_COMMON, 'root_lists')

def browse_genre(genre_id):
    """Retrieve video lists for a genre"""
    pass

@cache.cache_output(cache.CACHE_METADATA, 0, 'video_id',
                    ttl=common.CACHE_METADATA_TTL, to_disk=True)
def metadata(video_id):
    """Retrieve additional metadata for a video"""
    common.debug('Requesting metdata for {}'.format(video_id))
    return common.make_call(
        NetflixSession.get,
        {
            'component': 'metadata',
            'req_type': 'api',
            'params': {'movieid': video_id}
        })['video']

def episode_metadata(tvshowid, seasonid, episodeid):
    """Retrieve metadata for a single episode"""
    try:
        return common.find_episode(episodeid, metadata(tvshowid)['seasons'])
    except KeyError:
        # Episode metadata may not exist if its a new episode and cached data
        # is outdated. In this case, invalidate the cache entry and try again
        # safely (if it doesn't exist this time, there is no metadata for the
        # episode, so we assign an empty dict).
        cache.invalidate_entry(cache.CACHE_METADATA, tvshowid)
        return (metadata(tvshowid).get('seasons', {}).get(seasonid, {})
                .get('episodes', {}).get(episodeid, {}))

def build_paths(base_path, partial_paths):
    """Build a list of full paths by concatenating each partial path
    with the base path"""
    paths = [base_path + partial_path for partial_path in partial_paths]
    common.debug(json.dumps(paths))
    return paths
