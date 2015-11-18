# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""
Implements several handle backends
"""
import logging

from rdflib import Graph, Literal, RDF

from datalad.support.collectionrepo import CollectionRepo
from datalad.support.exceptions import ReadOnlyBackendError
from datalad.support.handle import Handle
from datalad.support.handlerepo import HandleRepo, lgr
from datalad.support.metadatahandler import DLNS
from datalad.utils import get_local_file_url

lgr = logging.getLogger('datalad.handlebackends')


# TODO: Both of the repo backends for handles share a lot of code.
# So, there probably should be a super class to contain that code and the sub
# classes just hold different paths and may be redirect some calls to
# differently named methods of the underlying repo.

class HandleRepoBackend(Handle):
    # TODO: Name. See corresponding naming for CollectionBackend and find
    # a solution for both of them
    """Handle backend for handle repositories.

    Implements a Handle pointing to a handle repository branch.
    """

    def __init__(self, repo, branch=None, files=None):
        """

        :param repo:
        :param branch:
        :param files:
        :return:
        """

        super(HandleRepoBackend, self).__init__()

        if not isinstance(repo, HandleRepo):
            e_msg = "Can't deal with type %s to access a handle repository." \
                    % type(repo)
            lgr.error(e_msg)
            raise TypeError(e_msg)
        else:
            self.repo = repo

        if branch is None:
            self._branch = self.repo.git_get_active_branch()
        elif branch in self.repo.git_get_branches() + \
                self.repo.git_get_remote_branches():
            self._branch = branch
        else:
            raise ValueError("Unknown branch '%s' of repository at %s." %
                             (branch, self.repo.path))

        # we can't write to a remote branch:
        self.is_read_only = self._branch.split('/')[0] in \
                            self.repo.git_get_remotes()
        self._files = files
        self._sub_graphs = dict()

    def get_subgraphs(self):
        if self._sub_graphs == dict():
            self.update_metadata()
        return self._sub_graphs

    def set_subgraphs(self, graphs):
        if not isinstance(graphs, dict):
            raise TypeError("Unexpected type of data: %s. "
                            "Expects a dictionary of sub-graphs." %
                            type(graphs))
        for subgraph in graphs:
            if not isinstance(graphs[subgraph], Graph):
                raise TypeError("Sub-graph '%s' is of type %s. "
                                "Expected: rdflib.Graph." %
                                (subgraph, type(graphs[subgraph])))
            self._sub_graphs[subgraph] = graphs[subgraph]

    sub_graphs = property(get_subgraphs, set_subgraphs)

    def set_metadata(self, data):
        """

        :param data: dict of Graph
        :return:
        """
        self.sub_graphs = data

    def get_metadata(self):
        """

        :return:
        """
        self._graph = Graph(identifier=Literal(self.repo.name))
        for key in self.sub_graphs:
            self._graph += self.sub_graphs[key]

        return self._graph

    meta = property(get_metadata, set_metadata)

    def update_metadata(self):
        """

        :return:
        """
        self.sub_graphs = self.repo.get_metadata(self._files,
                                                 branch=self._branch)

    def commit_metadata(self, msg="Handle metadata updated."):
        """

        :param msg:
        :return:
        """
        if self.is_read_only:
            raise ReadOnlyBackendError("Can't commit to handle '%s'.\n"
                                       "(Repository: %s\tBranch: %s)" %
                                       (self.name, self.repo.path,
                                        self._branch))

        self.repo.set_metadata(self.sub_graphs, msg=msg, branch=self._branch)

    @property
    def url(self):
        """

        :return:
        """
        return get_local_file_url(self.repo.path)

    # TODO: set_name? See Handle.


class CollectionRepoHandleBackend(Handle):
    """Handle backend for collection repositories.

    Implements a Handle backend retrieving its data from a branch of a
    collection repository.
    """

    def __init__(self, repo, key, branch=None, files=None):
        """

        :param repo:
        :param key:
        :param branch:
        :param files:
        :return:
        """
        super(CollectionRepoHandleBackend, self).__init__()

        if not isinstance(repo, CollectionRepo):
            e_msg = "Can't deal with type %s to access " \
                    "a collection repository." % type(repo)
            lgr.error(e_msg)
            raise TypeError(e_msg)
        else:
            self.repo = repo

        if branch is None:
            self._branch = self.repo.git_get_active_branch()
        elif branch in self.repo.git_get_branches() + \
                self.repo.git_get_remote_branches():
            self._branch = branch
        else:
            raise ValueError("Unknown branch %s of repository at %s." %
                             (branch, self.repo.path))

        if key not in self.repo.get_handle_list(self._branch):
            raise ValueError("Unknown handle %s in branch %s of repository %s."
                             % (key, self._branch, self.repo.path))
        self._key = key

        # we can't write to a remote branch:
        self.is_read_only = self._branch.split('/')[0] in \
                            self.repo.git_get_remotes()

        self._files = files
        self._sub_graphs = dict()

    def get_subgraphs(self):
        if self._sub_graphs == dict():
            self.update_metadata()
        return self._sub_graphs

    def set_subgraphs(self, graphs):
        if not isinstance(graphs, dict):
            raise TypeError("Unexpected type of data: %s. "
                            "Expects a dictionary of sub-graphs." %
                            type(graphs))
        for subgraph in graphs:
            if not isinstance(graphs[subgraph], Graph):
                raise TypeError("Sub-graph '%s' is of type %s. "
                                "Expected: rdflib.Graph." %
                                (subgraph, type(graphs[subgraph])))
            self._sub_graphs[subgraph] = graphs[subgraph]

    sub_graphs = property(get_subgraphs, set_subgraphs)

    def set_metadata(self, data):
        """

        :param data: dict of Graph
        :return:
        """
        self.sub_graphs = data

    def get_metadata(self):
        """

        :return:
        """
        self._graph = Graph(identifier=Literal(self._key))
        for key in self.sub_graphs:
            self._graph += self.sub_graphs[key]

        return self._graph

    meta = property(get_metadata, set_metadata)

    def update_metadata(self):
        self.sub_graphs = self.repo.get_handle_graphs(self._key,
                                                      branch=self._branch,
                                                      files=self._files)

    def commit_metadata(self, msg="Handle metadata updated."):
        if self.is_read_only:
            raise ReadOnlyBackendError("Can't commit to handle '%s'.\n"
                                       "(Repository: %s\tBranch: %s." %
                                       (self.name, self.repo.path,
                                        self._branch))

        # TODO: different graphs, file names, etc. See CollectionRepo
        # Same goes for HandleRepo/HandleRepoBackend
        self.repo.store_handle_graphs(self.sub_graphs, self._key,
                                      branch=self._branch, msg=msg)

    # TODO: set_name? See Handle.

    @property
    def url(self):
        return str(self.meta.value(predicate=RDF.type, object=DLNS.Handle))