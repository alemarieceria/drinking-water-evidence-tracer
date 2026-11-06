"""The extraction page delegates to a replaceable, offline-tested service."""

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

from app.extraction import ExtractionService
from app.main import app, get_extraction_service
from app.models import ExtractionResponse
from tests.test_extraction_agent import CountingModel
from tests.test_extraction_service import service_setup as service_setup


@pytest.fixture
def extraction_client(service_setup):
    root, _, runs, output = service_setup
    model = CountingModel(output)
    service = ExtractionService(root, runs, model)
    app.dependency_overrides[get_extraction_service] = lambda: service
    try:
        with TestClient(app) as client:
            yield client, model
    finally:
        app.dependency_overrides.clear()


def test_separate_page_has_labeled_inputs_and_unconfirmed_notice(extraction_client) -> None:
    client, _ = extraction_client
    response = client.get('/extract')
    assert response.status_code == 200
    assert 'name="doc_id"' in response.text
    assert 'for="doc-id"' in response.text
    assert 'unconfirmed' in response.text.lower()
    assert client.get('/static/extraction.js').status_code == 200
    assert client.get('/static/../.env').status_code == 404
    assert client.get('/runs').status_code == 404


def test_post_uses_service_and_preserves_raw_results(extraction_client) -> None:
    client, model = extraction_client
    response = client.post('/extract',json={'doc_id':'DOC-0001','results_page':1,'definitions_page':2})
    assert response.status_code == 200
    data = response.json()
    assert data['total_rows']==1 and data['status']=='success'
    assert data['rows'][0]['result_as_written']=='0.27'
    assert data['rows'][0]['mdl'] is None
    assert data['rows'][0]['review_status']=='unconfirmed'
    assert model.calls==1
    assert 'fake-test-secret' not in response.text


@pytest.mark.parametrize('payload',[
    {'doc_id':'../../.env','results_page':1,'definitions_page':2},
    {'doc_id':'DOC-0001','results_page':True,'definitions_page':2},
    {'doc_id':'DOC-0001','results_page':0,'definitions_page':2},
    {'doc_id':'DOC-0001','results_page':'1','definitions_page':2},
])
def test_invalid_input_never_calls_model(extraction_client,payload) -> None:
    client, model = extraction_client
    assert client.post('/extract',json=payload).status_code==422
    assert model.calls==0


@pytest.mark.parametrize('code,status',[
    ('unknown_document',404),('missing_file',404),('changed_file',409),
    ('invalid_page',422),('unreadable_pdf',422),('empty_page',422),
    ('configuration_error',503),('storage_error',503),('archive_unavailable',503),
    ('model_failure',502),('model_timeout',504),('input_too_large',422),
])
def test_safe_errors_have_appropriate_http_status(code,status) -> None:
    class FailedService:
        async def run(self,request):
            return ExtractionResponse(request=request,status='error',error_code=code,message='Safe error')

    app.dependency_overrides[get_extraction_service]=lambda: FailedService()
    try:
        with TestClient(app) as client:
            response=client.post('/extract',json={'doc_id':'DOC-0001','results_page':1,'definitions_page':2})
        assert response.status_code==status
        assert response.json()['rows']==[]
        assert response.json()['error_code']==code
    finally:
        app.dependency_overrides.clear()


def test_unclear_output_has_no_success_rows(service_setup) -> None:
    root, _, runs, _ = service_setup
    service=ExtractionService(root,runs,TestModel(custom_output_args={'status':'unclear','reason':'uncertain','rows':[]}))
    app.dependency_overrides[get_extraction_service]=lambda: service
    try:
        with TestClient(app) as client:
            response=client.post('/extract',json={'doc_id':'DOC-0001','results_page':1,'definitions_page':2})
        assert response.status_code==200
        assert response.json()['status']=='unclear'
        assert response.json()['total_rows']==0
    finally:
        app.dependency_overrides.clear()
