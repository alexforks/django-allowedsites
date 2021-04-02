# -*- coding: utf-8 -*-
from django.core.cache import cache


class ForceAllowedHostCheck(object):
    def process_request(self, request):
        request.get_host()
        return None


class Sites(object):
    """
    Sites are unordered, because seriously who cares.
    """

    __slots__ = ('defaults', 'dynamic_public_ip', 'net_timeout',)

    def __init__(self, defaults=None, dynamic_public_ip=False, net_timeout=5):
        """
        :param defaults: None
        :param dynamic_public_ip: False - whether to detect the runtime public IP address and add it to ALLOWED_HOSTS.
        :param net_timeout: 5 (seconds) - the timeout for the network request to get the server's public IP address.
        """
        if defaults is None:
            defaults = ()
        self.defaults = frozenset(defaults)
        self.dynamic_public_ip = dynamic_public_ip
        self.net_timeout = net_timeout

    def get_public_ip(self):
        import requests
        public_ip = None
        try:
            public_ip = requests.get('http://checkip.amazonaws.com', timeout=self.net_timeout).text.rstrip('\n')
        except requests.exceptions.RequestException:
            pass
        return public_ip

    def get_raw_sites(self):
        from django.contrib.sites.models import Site
        return Site.objects.all().iterator()

    def get_domains(self):
        """
        Yields domains *without* any ports defined, as that's what
        `validate_host` wants
        """
        from django.http.request import split_domain_port
        raw_sites = self.get_raw_sites()
        domains = set()
        raw_domains = (site.domain for site in raw_sites)
        for domain in raw_domains:
            domain_host, domain_port = split_domain_port(domain)
            domains.add(domain_host)
        if self.dynamic_public_ip:
            public_ip = self.get_public_ip()
            if public_ip:
                domains.add(public_ip)
        return frozenset(domains)

    def get_merged_allowed_hosts(self):
        sites = self.get_domains()
        return self.defaults.union(sites)

    def __iter__(self):
        return iter(self.get_merged_allowed_hosts())

    def __repr__(self):
        return '<{mod}.{cls} for sites: {sites}>'.format(
            mod=self.__class__.__module__, cls=self.__class__.__name__,
            sites=str(self))

    def __str__(self):
        return ', '.join(self.get_merged_allowed_hosts())

    __unicode__ = __str__

    def __contains__(self, other):
        if other in self.defaults:
            return True
        if other in self.get_domains():
            return True
        return False

    def __len__(self):
        return len(self.get_merged_allowed_hosts())

    def __nonzero__(self):
        # ask in order, so that a query *may* not be necessary.
        if len(self.defaults) > 0:
            return True
        if len(self.get_domains()) > 0:
            return True
        return False

    __bool__ = __nonzero__

    def __eq__(self, other):
        # fail early.
        if self.defaults != other.defaults:
            return False
        side_a = self.get_merged_allowed_hosts()
        side_b = other.get_merged_allowed_hosts()
        return side_a == side_b

    def __add__(self, other):
        more_defaults = self.defaults.union(other.defaults)
        return self.__class__(defaults=more_defaults)

    def __sub__(self, other):
        less_defaults = self.defaults.difference(other.defaults)
        return self.__class__(defaults=less_defaults)


class AllowedSites(Sites):
    """
    This only exists to allow isinstance to differentiate between
    the various Site subclasses
    """
    __slots__ = ()


class CachedAllowedSites(Sites):
    """
    Sets the given ``Site`` domains into the ``default`` cache.
    Expects the cache to be shared between processes, such that
    a signal listening for ``Site`` creates will be able to add to
    the cache's contents for other processes to pick up on.
    """
    __slots__ = ('cache_timeout',)
    key = 'allowedsites'

    def __init__(self, cache_timeout=None, **kwargs):
        """
        :param args:
        :param cache_timeout: None (forever) - for how long the cache will last, in seconds.
        :param kwargs:
        """
        self.cache_timeout = cache_timeout
        super(CachedAllowedSites, self).__init__(*args, **kwargs)

    def _get_cached_sites(self):
        results = cache.get(self.key, None)
        return results

    def get_merged_allowed_hosts(self):
        sites = self._get_cached_sites()
        if sites is None:
            sites = self._set_cached_sites()
        return self.defaults.union(sites)

    def _set_cached_sites(self, **kwargs):
        """
        Forces whatever is in the DB into the cache.
        """
        in_db = self.get_domains()
        cache.set(self.key, in_db, self.cache_timeout)
        return in_db

    def update_cache(self, **kwargs):
        """
        May be used as a post_save or post_delete signal listener.
        Replaces whatever is in the cache with the sites in the DB
        *at this moment*
        """
        self._set_cached_sites(**kwargs)

    @classmethod
    def clear_cache(cls):
        """
        May be used as a post_save or post_delete signal listener.
        Clears whatever is in the cache.
        """
        cache.delete(cls.key)
