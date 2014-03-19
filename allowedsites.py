# -*- coding: utf-8 -*-

class Sites(object):
    """
    Sites are unordered, because seriously who cares.
    """
    
    __slots__ = ('defaults',)
    
    def __init__(self, defaults=None):
        if defaults is None:
            defaults = ()
        self.defaults = frozenset(defaults)
        
    def get_raw_sites(self):
        from django.contrib.sites.models import Site
        return Site.objects.all().iterator()
        
    def get_sites(self):
        raw_sites = self.get_raw_sites()
        return frozenset(site.domain for site in raw_sites)
        
    def get_merged_allowed_hosts(self):
        sites = self.get_sites()
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
        if other in self.get_sites():
            return True
        return False
    
    def __len__(self):
        return len(self.get_merged_allowed_hosts())
        
    def __nonzero__(self):
        # ask in order, so that a query *may* not be necessary.
        if len(self.defaults) > 0:
            return True
        if len(self.get_sites()) > 0:
            return True
        return False
        
    __bool__ = __nonzero__
        
    def __eq__(self, other):
        return self.defaults == other.defaults
        
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
    __slots__ = ('defaults',)
    pass


class CachedAllowedSites(Sites):
    """
    Sets the given ``Site`` domains into the ``default`` cache.
    Expects the cache to be shared between processes, such that
    a signal listening for ``Site`` creates will be able to add to
    the cache's contents for other processes to pick up on.
    """
    __slots__ = ('defaults', 'key')
    
    def __init__(self, defaults=None, key='allowedsites'):
        super(CachedAllowedSites, self).__init__(defaults=defaults)
        self.key = key
    
    def get_cached_sites(self):
        from django.core.cache import cache
        results = cache.get(self.key)
        return results

    def get_sites(self):
        cached = self.get_cached_sites()
        if cached is None:
            cached = super(CachedAllowedSites, self).get_sites()
            cache.set(self.key, cached)
        return cached
    
    def get_merged_allowed_hosts(self):
        sites = self.get_sites()
        return self.defaults.union(sites)
