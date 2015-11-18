# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Test implementation of classes HandleRepoBackend and
CollectionRepoHandleBackend.
"""
from genericpath import exists
from os.path import join as opj

from nose.tools import eq_, assert_raises, assert_in, ok_, assert_not_in, \
    assert_false, assert_equal
from rdflib import Graph, Literal, URIRef, RDF

from datalad.consts import REPO_STD_META_FILE, HANDLE_META_DIR
from datalad.support.annexrepo import AnnexRepo
from datalad.support.collectionrepo import CollectionRepo
from datalad.support.exceptions import ReadOnlyBackendError
from datalad.support.gitrepo import GitRepo
from datalad.support.handle_backends import HandleRepoBackend, \
    CollectionRepoHandleBackend
from datalad.support.handlerepo import HandleRepo
from datalad.support.metadatahandler import DLNS
from datalad.tests.utils import with_testrepos, ok_startswith, with_tempfile, \
    ok_clean_git
from datalad.utils import get_local_file_url


@with_testrepos('.*handle.*', flavors=['local'])
def test_HandleRepoBackend_constructor(path):
    repo = HandleRepo(path, create=False)
    backend = HandleRepoBackend(repo)
    eq_(backend._branch, repo.git_get_active_branch())
    eq_(backend.repo, repo)
    eq_(backend.url, get_local_file_url(repo.path))
    eq_(backend.is_read_only, False)
    eq_("<Handle name=%s "
        "(<class 'datalad.support.handle_backends.HandleRepoBackend'>)>"
        % backend.name,
        backend.__repr__())

    # not existing branch:
    with assert_raises(ValueError) as cm:
        HandleRepoBackend(repo, branch="something")
    ok_startswith(str(cm.exception), "Unknown branch")

    # wrong source class:
    with assert_raises(TypeError) as cm:
        HandleRepoBackend(AnnexRepo(path, create=False))
    ok_startswith(str(cm.exception),
                  "Can't deal with type "
                  "<class 'datalad.support.annexrepo.AnnexRepo'>")


@with_testrepos('.*handle.*', flavors=['local'])
def test_HandleRepoBackend_name(path):
    repo = HandleRepo(path, create=False)
    backend = HandleRepoBackend(repo)

    # get name:
    eq_(backend.name, repo.name)
    # set name:
    with assert_raises(AttributeError) as cm:
        backend.name = "new_name"


@with_testrepos('.*handle.*', flavors=['clone'])
@with_tempfile
def test_HandleRepoBackend_meta(url, path):
    repo = HandleRepo(path, url, create=True)

    repo_graph = Graph(identifier=Literal(repo.name))
    repo_graphs = repo.get_metadata()
    for key in repo_graphs:
        repo_graph += repo_graphs[key]

    backend = HandleRepoBackend(repo)

    eq_(set(backend.sub_graphs.keys()), set(repo_graphs.keys()))
    for key in backend.sub_graphs.keys():
        eq_(set(iter(backend.sub_graphs[key])),
            set(iter(repo_graphs[key])))
    eq_(backend.meta, repo_graph)

    # modify metadata:
    triple_1 = (URIRef("http://example.org/whatever"), RDF.type, DLNS.FakeTerm)
    triple_2 = (URIRef("http://example.org/whatever"), RDF.type,
                DLNS.AnotherFakeTerm)
    backend.sub_graphs[REPO_STD_META_FILE[:-4]].add(triple_1)
    test_file = opj(path, HANDLE_META_DIR, "test.ttl")
    backend.sub_graphs['test'] = Graph()
    backend.sub_graphs['test'].add(triple_2)

    assert_in(triple_1, backend.meta)
    assert_in(triple_2, backend.meta)

    # commit:
    backend.commit_metadata()

    ok_clean_git(path, annex=True)
    ok_(exists(test_file))
    test_graph_from_file = Graph().parse(test_file, format="turtle")
    eq_(set(iter(backend.sub_graphs['test'])),
        set(iter(test_graph_from_file)))
    assert_in(triple_2, test_graph_from_file)
    assert_not_in(triple_1, test_graph_from_file)

    # If read only, should raise exception:
    backend.is_read_only = True
    assert_raises(ReadOnlyBackendError, backend.commit_metadata)


# TODO: test remotes


@with_tempfile
@with_tempfile
@with_tempfile
@with_tempfile
def test_CollectionRepoHandleBackend_constructor(path1, path2, h1_path, h2_path):

    # setup
    clt = CollectionRepo(path1, name='testcollection')
    clt2 = CollectionRepo(path2, name='testcollection2')
    h1 = HandleRepo(h1_path)
    h2 = HandleRepo(h2_path)
    clt.add_handle(h1, "handle1")
    clt2.add_handle(h2, "handle2")
    clt.git_remote_add("remoterepo", path2)
    clt.git_fetch("remoterepo")

    # constructors to test:
    be1 = CollectionRepoHandleBackend(clt, "handle1")
    be2 = CollectionRepoHandleBackend(clt, "handle1", "master")
    be3 = CollectionRepoHandleBackend(clt, "handle2", "remoterepo/master")

    with assert_raises(ValueError) as cm:
        CollectionRepoHandleBackend(clt, "NotExisting")
    ok_startswith(str(cm.exception), "Unknown handle NotExisting")

    with assert_raises(ValueError) as cm:
        CollectionRepoHandleBackend(clt, "handle1", branch="NotExisting")
    ok_startswith(str(cm.exception), "Unknown branch NotExisting")

    with assert_raises(TypeError) as cm:
        CollectionRepoHandleBackend(GitRepo(path1, create=False), "handle1")
    ok_startswith(str(cm.exception),
                  "Can't deal with type "
                  "<class 'datalad.support.gitrepo.GitRepo'>")

    assert_false(be1.is_read_only)
    assert_false(be2.is_read_only)
    ok_(be3.is_read_only)

    assert_equal(be1.url, get_local_file_url(h1_path))
    assert_equal(be2.url, get_local_file_url(h1_path))
    assert_equal(be3.url, get_local_file_url(h2_path))

    for backend in [be1, be2, be3]:
        eq_("<Handle name=%s (<class "
            "'datalad.support.handle_backends.CollectionRepoHandleBackend'>)>"
            % backend.name,
            backend.__repr__())


@with_testrepos('collection', flavors=['local'])
def test_CollectionRepoHandleBackend_name(path):
    repo = CollectionRepo(path, create=False)
    backend = CollectionRepoHandleBackend(repo, "BasicHandle")

    # get name:
    eq_(backend.name, "BasicHandle")
    # set name:
    with assert_raises(AttributeError) as cm:
        backend.name = "new_name"


@with_testrepos('collection', flavors=['clone'])
@with_tempfile
def test_CollectionRepoHandleBackend_meta(url, path):
    repo = CollectionRepo(path, url, create=True)

    repo_graph = Graph(identifier=Literal("BasicHandle"))
    repo_graphs = repo.get_handle_graphs("BasicHandle")
    for key in repo_graphs:
        repo_graph += repo_graphs[key]

    backend = CollectionRepoHandleBackend(repo, "BasicHandle")

    eq_(backend.sub_graphs.keys(), repo_graphs.keys())
    for key in backend.sub_graphs.keys():
        eq_(set(iter(backend.sub_graphs[key])),
            set(iter(repo_graphs[key])))
    eq_(backend.meta, repo_graph)

    # modify metadata:
    triple_1 = (URIRef("http://example.org/whatever"), RDF.type, DLNS.FakeTerm)
    triple_2 = (URIRef("http://example.org/whatever"), RDF.type,
                DLNS.AnotherFakeTerm)
    backend.sub_graphs[REPO_STD_META_FILE[:-4]].add(triple_1)
    test_file = opj(path, repo._key2filename("BasicHandle"), "test.ttl")
    backend.sub_graphs['test'] = Graph()
    backend.sub_graphs['test'].add(triple_2)

    assert_in(triple_1, backend.meta)
    assert_in(triple_2, backend.meta)

    # commit:
    backend.commit_metadata()

    ok_clean_git(path, annex=False)
    ok_(exists(test_file))
    test_graph_from_file = Graph().parse(test_file, format="turtle")
    eq_(set(iter(backend.sub_graphs['test'])),
        set(iter(test_graph_from_file)))
    assert_in(triple_2, test_graph_from_file)
    assert_not_in(triple_1, test_graph_from_file)

    # If read only, should raise exception:
    backend.is_read_only = True
    assert_raises(ReadOnlyBackendError, backend.commit_metadata)