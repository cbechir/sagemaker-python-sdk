# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
from __future__ import absolute_import

import pytest
import urllib3
import os
from botocore.exceptions import ClientError
from mock import Mock, patch
from tests.unit import DATA_DIR

import sagemaker
from sagemaker.workflow.parameters import ParameterString
from sagemaker.workflow.pipeline import Pipeline
from tests.unit.sagemaker.workflow.helpers import CustomStep
from sagemaker.local.local_session import LocalSession
from sagemaker.local.entities import _LocalPipelineExecution


OK_RESPONSE = urllib3.HTTPResponse()
OK_RESPONSE.status = 200

BAD_RESPONSE = urllib3.HTTPResponse()
BAD_RESPONSE.status = 502

ENDPOINT_CONFIG_NAME = "test-endpoint-config"
PRODUCTION_VARIANTS = [{"InstanceType": "ml.c4.99xlarge", "InitialInstanceCount": 10}]

MODEL_NAME = "test-model"
PRIMARY_CONTAINER = {"ModelDataUrl": "/some/model/path", "Environment": {"env1": 1, "env2": "b"}}

ENDPOINT_URL = "http://127.0.0.1:9000"
BUCKET_NAME = "mybucket"
LS_FILES = {"Contents": [{"Key": "/data/test.csv"}]}


@patch("sagemaker.local.image._SageMakerContainer.process")
@patch("sagemaker.local.local_session.LocalSession")
def test_create_processing_job(process, LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    instance_count = 2
    image = "my-docker-image:1.0"

    app_spec = {"ImageUri": image}
    resource_config = {"ClusterConfig": {"InstanceCount": instance_count, "InstanceType": "local"}}
    environment = {"Var1": "Value1"}
    processing_inputs = [
        {
            "InputName": "input1",
            "S3Input": {
                "LocalPath": "/opt/ml/processing/input/input1",
                "S3Uri": "s3://some-bucket/some-path/input1",
                "S3DataDistributionType": "FullyReplicated",
                "S3InputMode": "File",
            },
        },
        {
            "InputName": "input2",
            "S3Input": {
                "LocalPath": "/opt/ml/processing/input/input2",
                "S3Uri": "s3://some-bucket/some-path/input2",
                "S3DataDistributionType": "FullyReplicated",
                "S3CompressionType": "None",
                "S3InputMode": "File",
            },
        },
    ]
    processing_output_config = {
        "Outputs": [
            {
                "OutputName": "output1",
                "S3Output": {
                    "LocalPath": "/opt/ml/processing/output/output1",
                    "S3Uri": "s3://some-bucket/some-path/output1",
                    "S3UploadMode": "EndOfJob",
                },
            }
        ]
    }

    local_sagemaker_client.create_processing_job(
        "my-processing-job",
        app_spec,
        resource_config,
        environment,
        processing_inputs,
        processing_output_config,
    )

    expected = {
        "ProcessingJobArn": "my-processing-job",
        "ProcessingJobName": "my-processing-job",
        "AppSpecification": {
            "ImageUri": image,
            "ContainerEntrypoint": None,
            "ContainerArguments": None,
        },
        "Environment": {"Var1": "Value1"},
        "ProcessingResources": {
            "ClusterConfig": {
                "InstanceCount": instance_count,
                "InstanceType": "local",
                "VolumeSizeInGB": 30,
                "VolumeKmsKeyId": None,
            }
        },
        "RoleArn": "<no_role>",
        "StoppingCondition": {"MaxRuntimeInSeconds": 86400},
        "ProcessingJobStatus": "Completed",
    }

    response = local_sagemaker_client.describe_processing_job("my-processing-job")

    assert response["ProcessingJobArn"] == expected["ProcessingJobArn"]
    assert response["ProcessingJobName"] == expected["ProcessingJobName"]
    assert response["AppSpecification"]["ImageUri"] == expected["AppSpecification"]["ImageUri"]
    assert response["AppSpecification"]["ContainerEntrypoint"] is None
    assert response["AppSpecification"]["ContainerArguments"] is None
    assert response["Environment"]["Var1"] == expected["Environment"]["Var1"]
    assert (
        response["ProcessingResources"]["ClusterConfig"]["InstanceCount"]
        == expected["ProcessingResources"]["ClusterConfig"]["InstanceCount"]
    )
    assert (
        response["ProcessingResources"]["ClusterConfig"]["InstanceType"]
        == expected["ProcessingResources"]["ClusterConfig"]["InstanceType"]
    )
    assert response["ProcessingJobStatus"] == expected["ProcessingJobStatus"]


@patch("sagemaker.local.image._SageMakerContainer.process")
@patch("sagemaker.local.local_session.LocalSession")
def test_create_processing_job_not_fully_replicated(process, LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    instance_count = 2
    image = "my-docker-image:1.0"

    app_spec = {"ImageUri": image}
    resource_config = {"ClusterConfig": {"InstanceCount": instance_count, "InstanceType": "local"}}
    environment = {"Var1": "Value1"}
    processing_inputs = [
        {
            "InputName": "input1",
            "S3Input": {
                "LocalPath": "/opt/ml/processing/input/input1",
                "S3Uri": "s3://some-bucket/some-path/input1",
                "S3DataDistributionType": "ShardedByS3Key",
                "S3InputMode": "File",
            },
        },
        {
            "InputName": "input2",
            "S3Input": {
                "LocalPath": "/opt/ml/processing/input/input2",
                "S3Uri": "s3://some-bucket/some-path/input2",
                "S3DataDistributionType": "ShardedByS3Key",
                "S3CompressionType": "None",
                "S3InputMode": "File",
            },
        },
    ]
    processing_output_config = {
        "Outputs": [
            {
                "OutputName": "output1",
                "S3Output": {
                    "LocalPath": "/opt/ml/processing/output/output1",
                    "S3Uri": "s3://some-bucket/some-path/output1",
                    "S3UploadMode": "EndOfJob",
                },
            }
        ]
    }
    with pytest.raises(RuntimeError):
        local_sagemaker_client.create_processing_job(
            "my-processing-job",
            app_spec,
            resource_config,
            environment,
            processing_inputs,
            processing_output_config,
        )


@patch("sagemaker.local.image._SageMakerContainer.process")
@patch("sagemaker.local.local_session.LocalSession")
def test_create_processing_job_invalid_upload_mode(process, LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    instance_count = 2
    image = "my-docker-image:1.0"

    app_spec = {"ImageUri": image}
    resource_config = {"ClusterConfig": {"InstanceCount": instance_count, "InstanceType": "local"}}
    environment = {"Var1": "Value1"}
    processing_inputs = [
        {
            "InputName": "input1",
            "S3Input": {
                "LocalPath": "/opt/ml/processing/input/input1",
                "S3Uri": "s3://some-bucket/some-path/input1",
                "S3DataDistributionType": "FullyReplicated",
                "S3InputMode": "File",
            },
        },
        {
            "InputName": "input2",
            "S3Input": {
                "LocalPath": "/opt/ml/processing/input/input2",
                "S3Uri": "s3://some-bucket/some-path/input2",
                "S3DataDistributionType": "FullyReplicated",
                "S3CompressionType": "None",
                "S3InputMode": "File",
            },
        },
    ]
    processing_output_config = {
        "Outputs": [
            {
                "OutputName": "output1",
                "S3Output": {
                    "LocalPath": "/opt/ml/processing/output/output1",
                    "S3Uri": "s3://some-bucket/some-path/output1",
                    "S3UploadMode": "Continuous",
                },
            }
        ]
    }
    with pytest.raises(RuntimeError):
        local_sagemaker_client.create_processing_job(
            "my-processing-job",
            app_spec,
            resource_config,
            environment,
            processing_inputs,
            processing_output_config,
        )


@patch("sagemaker.local.image._SageMakerContainer.process")
@patch("sagemaker.local.local_session.LocalSession")
def test_create_processing_job_invalid_processing_input(process, LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    instance_count = 2
    image = "my-docker-image:1.0"

    app_spec = {"ImageUri": image}
    resource_config = {"ClusterConfig": {"InstanceCount": instance_count, "InstanceType": "local"}}
    environment = {"Var1": "Value1"}
    processing_inputs = [
        {
            "InputName": "input1",
            "DatasetDefinition": {
                "AthenaDatasetDefinition": {
                    "Catalog": "cat1",
                    "Database": "db1",
                    "OutputS3Uri": "s3://bucket_name/prefix/",
                    "QueryString": "SELECT * FROM SOMETHING",
                },
                "DataDistributionType": "FullyReplicated",
                "InputMode": "File",
                "LocalPath": "/opt/ml/processing/input/athena",
            },
        }
    ]
    processing_output_config = {
        "Outputs": [
            {
                "OutputName": "output1",
                "S3Output": {
                    "LocalPath": "/opt/ml/processing/output/output1",
                    "S3Uri": "s3://some-bucket/some-path/output1",
                    "S3UploadMode": "Continuous",
                },
            }
        ]
    }
    with pytest.raises(RuntimeError):
        local_sagemaker_client.create_processing_job(
            "my-processing-job",
            app_spec,
            resource_config,
            environment,
            processing_inputs,
            processing_output_config,
        )


@patch("sagemaker.local.image._SageMakerContainer.process")
@patch("sagemaker.local.local_session.LocalSession")
def test_create_processing_job_invalid_processing_output(process, LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    instance_count = 2
    image = "my-docker-image:1.0"

    app_spec = {"ImageUri": image}
    resource_config = {"ClusterConfig": {"InstanceCount": instance_count, "InstanceType": "local"}}
    environment = {"Var1": "Value1"}
    processing_inputs = [
        {
            "InputName": "input1",
            "S3Input": {
                "LocalPath": "/opt/ml/processing/input/input1",
                "S3Uri": "s3://some-bucket/some-path/input1",
                "S3DataDistributionType": "FullyReplicated",
                "S3InputMode": "File",
            },
        },
        {
            "InputName": "input2",
            "S3Input": {
                "LocalPath": "/opt/ml/processing/input/input2",
                "S3Uri": "s3://some-bucket/some-path/input2",
                "S3DataDistributionType": "FullyReplicated",
                "S3CompressionType": "None",
                "S3InputMode": "File",
            },
        },
    ]
    processing_output_config = {
        "Outputs": [
            {
                "OutputName": "output1",
                "FeatureStoreOutput": {"FeatureGroupName": "Group1"},
            }
        ]
    }
    with pytest.raises(RuntimeError):
        local_sagemaker_client.create_processing_job(
            "my-processing-job",
            app_spec,
            resource_config,
            environment,
            processing_inputs,
            processing_output_config,
        )


@patch("sagemaker.local.local_session.LocalSession")
def test_describe_invalid_processing_job(*args):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()
    with pytest.raises(ClientError):
        local_sagemaker_client.describe_processing_job("i-havent-created-this-job")


@patch("sagemaker.local.image._SageMakerContainer.train", return_value="/some/path/to/model")
@patch("sagemaker.local.local_session.LocalSession")
def test_create_training_job(train, LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    instance_count = 2
    image = "my-docker-image:1.0"

    algo_spec = {"TrainingImage": image}
    input_data_config = [
        {
            "ChannelName": "a",
            "DataSource": {
                "S3DataSource": {
                    "S3DataDistributionType": "FullyReplicated",
                    "S3Uri": "s3://my_bucket/tmp/source1",
                }
            },
        },
        {
            "ChannelName": "b",
            "DataSource": {
                "FileDataSource": {
                    "FileDataDistributionType": "FullyReplicated",
                    "FileUri": "file:///tmp/source1",
                }
            },
        },
    ]
    output_data_config = {}
    resource_config = {"InstanceType": "local", "InstanceCount": instance_count}
    hyperparameters = {"a": 1, "b": "bee"}

    local_sagemaker_client.create_training_job(
        "my-training-job",
        algo_spec,
        output_data_config,
        resource_config,
        InputDataConfig=input_data_config,
        HyperParameters=hyperparameters,
    )

    expected = {
        "ResourceConfig": {"InstanceCount": instance_count},
        "TrainingJobStatus": "Completed",
        "ModelArtifacts": {"S3ModelArtifacts": "/some/path/to/model"},
    }

    response = local_sagemaker_client.describe_training_job("my-training-job")

    assert response["TrainingJobStatus"] == expected["TrainingJobStatus"]
    assert (
        response["ResourceConfig"]["InstanceCount"] == expected["ResourceConfig"]["InstanceCount"]
    )
    assert (
        response["ModelArtifacts"]["S3ModelArtifacts"]
        == expected["ModelArtifacts"]["S3ModelArtifacts"]
    )


@patch("sagemaker.local.local_session.LocalSession")
def test_describe_invalid_training_job(*args):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()
    with pytest.raises(ClientError):
        local_sagemaker_client.describe_training_job("i-havent-created-this-job")


@patch("sagemaker.local.image._SageMakerContainer.train", return_value="/some/path/to/model")
@patch("sagemaker.local.local_session.LocalSession")
def test_create_training_job_invalid_data_source(train, LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    instance_count = 2
    image = "my-docker-image:1.0"

    algo_spec = {"TrainingImage": image}

    # InvalidDataSource is not supported. S3DataSource and FileDataSource are currently the only
    # valid Data Sources. We expect a ValueError if we pass this input data config.
    input_data_config = [
        {
            "ChannelName": "a",
            "DataSource": {
                "InvalidDataSource": {
                    "FileDataDistributionType": "FullyReplicated",
                    "FileUri": "ftp://myserver.com/tmp/source1",
                }
            },
        }
    ]

    output_data_config = {}
    resource_config = {"InstanceType": "local", "InstanceCount": instance_count}
    hyperparameters = {"a": 1, "b": "bee"}

    with pytest.raises(ValueError):
        local_sagemaker_client.create_training_job(
            "my-training-job",
            algo_spec,
            output_data_config,
            resource_config,
            InputDataConfig=input_data_config,
            HyperParameters=hyperparameters,
        )


@patch("sagemaker.local.image._SageMakerContainer.train", return_value="/some/path/to/model")
@patch("sagemaker.local.local_session.LocalSession")
def test_create_training_job_not_fully_replicated(train, LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    instance_count = 2
    image = "my-docker-image:1.0"

    algo_spec = {"TrainingImage": image}

    # Local Mode only supports FullyReplicated as Data Distribution type.
    input_data_config = [
        {
            "ChannelName": "a",
            "DataSource": {
                "S3DataSource": {
                    "S3DataDistributionType": "ShardedByS3Key",
                    "S3Uri": "s3://my_bucket/tmp/source1",
                }
            },
        }
    ]

    output_data_config = {}
    resource_config = {"InstanceType": "local", "InstanceCount": instance_count}
    hyperparameters = {"a": 1, "b": "bee"}

    with pytest.raises(RuntimeError):
        local_sagemaker_client.create_training_job(
            "my-training-job",
            algo_spec,
            output_data_config,
            resource_config,
            InputDataConfig=input_data_config,
            HyperParameters=hyperparameters,
        )


@patch("sagemaker.local.local_session.LocalSession")
def test_create_model(LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    local_sagemaker_client.create_model(MODEL_NAME, PRIMARY_CONTAINER)

    assert MODEL_NAME in sagemaker.local.local_session.LocalSagemakerClient._models


@patch("sagemaker.local.local_session.LocalSession")
def test_delete_model(LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    local_sagemaker_client.create_model(MODEL_NAME, PRIMARY_CONTAINER)
    assert MODEL_NAME in sagemaker.local.local_session.LocalSagemakerClient._models

    local_sagemaker_client.delete_model(MODEL_NAME)
    assert MODEL_NAME not in sagemaker.local.local_session.LocalSagemakerClient._models


@patch("sagemaker.local.local_session.LocalSession")
def test_describe_model(LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    with pytest.raises(ClientError):
        local_sagemaker_client.describe_model("model-does-not-exist")

    local_sagemaker_client.create_model(MODEL_NAME, PRIMARY_CONTAINER)
    response = local_sagemaker_client.describe_model(MODEL_NAME)

    assert response["ModelName"] == "test-model"
    assert response["PrimaryContainer"]["ModelDataUrl"] == "/some/model/path"


@patch("sagemaker.local.local_session._LocalTransformJob")
@patch("sagemaker.local.local_session.LocalSession")
def test_create_transform_job(LocalSession, _LocalTransformJob):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    local_sagemaker_client.create_transform_job("transform-job", "some-model", None, None, None)
    _LocalTransformJob().start.assert_called_with(None, None, None)

    local_sagemaker_client.describe_transform_job("transform-job")
    _LocalTransformJob().describe.assert_called()


@patch("sagemaker.local.local_session._LocalTransformJob")
@patch("sagemaker.local.local_session.LocalSession")
def test_describe_transform_job_does_not_exist(LocalSession, _LocalTransformJob):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    with pytest.raises(ClientError):
        local_sagemaker_client.describe_transform_job("transform-job-does-not-exist")


@patch("sagemaker.local.image._SageMakerContainer.process")
@patch("sagemaker.local.local_session.LocalSession")
def test_logs_for_job(process, LocalSession):
    local_job_logs = LocalSession.logs_for_job("my-processing-job")
    assert local_job_logs is not None


@patch("sagemaker.local.image._SageMakerContainer.process")
@patch("sagemaker.local.local_session.LocalSession")
def test_logs_for_processing_job(process, LocalSession):
    local_processing_job_logs = LocalSession.logs_for_processing_job("my-processing-job")
    assert local_processing_job_logs is not None


@patch("sagemaker.local.local_session.LocalSession")
def test_describe_endpoint_config(LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    # No Endpoint Config Created
    with pytest.raises(ClientError):
        local_sagemaker_client.describe_endpoint_config("some-endpoint-config")

    production_variants = [{"InstanceType": "ml.c4.99xlarge", "InitialInstanceCount": 10}]
    local_sagemaker_client.create_endpoint_config("test-endpoint-config", production_variants)

    response = local_sagemaker_client.describe_endpoint_config("test-endpoint-config")
    assert response["EndpointConfigName"] == "test-endpoint-config"
    assert response["ProductionVariants"][0]["InstanceType"] == "ml.c4.99xlarge"


@patch("sagemaker.local.local_session.LocalSession")
def test_create_endpoint_config(LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()
    local_sagemaker_client.create_endpoint_config(ENDPOINT_CONFIG_NAME, PRODUCTION_VARIANTS)

    assert (
        ENDPOINT_CONFIG_NAME in sagemaker.local.local_session.LocalSagemakerClient._endpoint_configs
    )


@patch("sagemaker.local.local_session.LocalSession")
def test_delete_endpoint_config(LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    local_sagemaker_client.create_endpoint_config(ENDPOINT_CONFIG_NAME, PRODUCTION_VARIANTS)
    assert (
        ENDPOINT_CONFIG_NAME in sagemaker.local.local_session.LocalSagemakerClient._endpoint_configs
    )

    local_sagemaker_client.delete_endpoint_config(ENDPOINT_CONFIG_NAME)
    assert (
        ENDPOINT_CONFIG_NAME
        not in sagemaker.local.local_session.LocalSagemakerClient._endpoint_configs
    )


@patch("sagemaker.local.image._SageMakerContainer.serve")
@patch("sagemaker.local.local_session.LocalSession")
@patch("urllib3.PoolManager.request")
@patch("sagemaker.local.local_session.LocalSagemakerClient.describe_endpoint_config")
@patch("sagemaker.local.local_session.LocalSagemakerClient.describe_model")
def test_describe_endpoint(describe_model, describe_endpoint_config, request, *args):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    request.return_value = OK_RESPONSE
    describe_endpoint_config.return_value = {
        "EndpointConfigName": "name",
        "EndpointConfigArn": "local:arn-does-not-matter",
        "CreationTime": "00:00:00",
        "ProductionVariants": [
            {
                "InitialVariantWeight": 1.0,
                "ModelName": "my-model",
                "VariantName": "AllTraffic",
                "InitialInstanceCount": 1,
                "InstanceType": "local",
            }
        ],
    }

    describe_model.return_value = {
        "ModelName": "my-model",
        "CreationTime": "00:00;00",
        "ExecutionRoleArn": "local:arn-does-not-matter",
        "ModelArn": "local:arn-does-not-matter",
        "PrimaryContainer": {
            "Environment": {"SAGEMAKER_REGION": "us-west-2"},
            "Image": "123.dkr.ecr-us-west-2.amazonaws.com/sagemaker-container:1.0",
            "ModelDataUrl": "s3://sagemaker-us-west-2/some/model.tar.gz",
        },
    }

    with pytest.raises(ClientError):
        local_sagemaker_client.describe_endpoint("non-existing-endpoint")

    local_sagemaker_client.create_endpoint("test-endpoint", "some-endpoint-config")
    response = local_sagemaker_client.describe_endpoint("test-endpoint")

    assert response["EndpointName"] == "test-endpoint"


@patch("sagemaker.local.image._SageMakerContainer.serve")
@patch("sagemaker.local.local_session.LocalSession")
@patch("urllib3.PoolManager.request")
@patch("sagemaker.local.local_session.LocalSagemakerClient.describe_endpoint_config")
@patch("sagemaker.local.local_session.LocalSagemakerClient.describe_model")
def test_create_endpoint(describe_model, describe_endpoint_config, request, *args):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()

    request.return_value = OK_RESPONSE
    describe_endpoint_config.return_value = {
        "EndpointConfigName": "name",
        "EndpointConfigArn": "local:arn-does-not-matter",
        "CreationTime": "00:00:00",
        "ProductionVariants": [
            {
                "InitialVariantWeight": 1.0,
                "ModelName": "my-model",
                "VariantName": "AllTraffic",
                "InitialInstanceCount": 1,
                "InstanceType": "local",
            }
        ],
    }

    describe_model.return_value = {
        "ModelName": "my-model",
        "CreationTime": "00:00;00",
        "ExecutionRoleArn": "local:arn-does-not-matter",
        "ModelArn": "local:arn-does-not-matter",
        "PrimaryContainer": {
            "Environment": {"SAGEMAKER_REGION": "us-west-2"},
            "Image": "123.dkr.ecr-us-west-2.amazonaws.com/sagemaker-container:1.0",
            "ModelDataUrl": "s3://sagemaker-us-west-2/some/model.tar.gz",
        },
    }

    local_sagemaker_client.create_endpoint("my-endpoint", "some-endpoint-config")

    assert "my-endpoint" in sagemaker.local.local_session.LocalSagemakerClient._endpoints


@patch("sagemaker.local.local_session.LocalSession")
def test_update_endpoint(LocalSession):
    local_sagemaker_client = sagemaker.local.local_session.LocalSagemakerClient()
    endpoint_name = "my-endpoint"
    endpoint_config = "my-endpoint-config"
    expected_error_message = "Update endpoint name is not supported in local session."
    with pytest.raises(NotImplementedError, match=expected_error_message):
        local_sagemaker_client.update_endpoint(endpoint_name, endpoint_config)


@patch("sagemaker.local.image._SageMakerContainer.serve")
@patch("urllib3.PoolManager.request")
def test_serve_endpoint_with_correct_accelerator(request, *args):
    mock_session = Mock(name="sagemaker_session")
    mock_session.return_value.sagemaker_client = Mock(name="sagemaker_client")
    mock_session.config = None

    request.return_value = OK_RESPONSE
    mock_session.sagemaker_client.describe_endpoint_config.return_value = {
        "ProductionVariants": [
            {
                "ModelName": "my-model",
                "InitialInstanceCount": 1,
                "InstanceType": "local",
                "AcceleratorType": "local_sagemaker_notebook",
            }
        ]
    }

    mock_session.sagemaker_client.describe_model.return_value = {
        "PrimaryContainer": {
            "Environment": {},
            "Image": "123.dkr.ecr-us-west-2.amazonaws.com/sagemaker-container:1.0",
            "ModelDataUrl": "s3://sagemaker-us-west-2/some/model.tar.gz",
        }
    }

    endpoint = sagemaker.local.local_session._LocalEndpoint(
        "my-endpoint", "some-endpoint-config", local_session=mock_session
    )
    endpoint.serve()

    assert (
        endpoint.primary_container["Environment"]["SAGEMAKER_INFERENCE_ACCELERATOR_PRESENT"]
        == "true"
    )


@patch("sagemaker.local.image._SageMakerContainer.serve")
@patch("urllib3.PoolManager.request")
def test_serve_endpoint_with_incorrect_accelerator(request, *args):
    mock_session = Mock(name="sagemaker_session")
    mock_session.return_value.sagemaker_client = Mock(name="sagemaker_client")
    mock_session.config = None

    request.return_value = OK_RESPONSE
    mock_session.sagemaker_client.describe_endpoint_config.return_value = {
        "ProductionVariants": [
            {
                "ModelName": "my-model",
                "InitialInstanceCount": 1,
                "InstanceType": "local",
                "AcceleratorType": "local",
            }
        ]
    }

    mock_session.sagemaker_client.describe_model.return_value = {
        "PrimaryContainer": {
            "Environment": {},
            "Image": "123.dkr.ecr-us-west-2.amazonaws.com/sagemaker-container:1.0",
            "ModelDataUrl": "s3://sagemaker-us-west-2/some/model.tar.gz",
        }
    }

    endpoint = sagemaker.local.local_session._LocalEndpoint(
        "my-endpoint", "some-endpoint-config", local_session=mock_session
    )
    endpoint.serve()

    with pytest.raises(KeyError):
        assert (
            endpoint.primary_container["Environment"]["SAGEMAKER_INFERENCE_ACCELERATOR_PRESENT"]
            == "true"
        )


def test_file_input_all_defaults():
    prefix = "pre"
    actual = sagemaker.local.local_session.file_input(fileUri=prefix)
    expected = {
        "DataSource": {
            "FileDataSource": {"FileDataDistributionType": "FullyReplicated", "FileUri": prefix}
        }
    }
    assert actual.config == expected


def test_file_input_content_type():
    prefix = "pre"
    actual = sagemaker.local.local_session.file_input(fileUri=prefix, content_type="text/csv")
    expected = {
        "DataSource": {
            "FileDataSource": {"FileDataDistributionType": "FullyReplicated", "FileUri": prefix}
        },
        "ContentType": "text/csv",
    }
    assert actual.config == expected


def test_local_session_is_set_to_local_mode():
    boto_session = Mock(region_name="us-west-2")
    local_session = sagemaker.local.local_session.LocalSession(boto_session=boto_session)
    assert local_session.local_mode


@pytest.fixture()
def sagemaker_session_custom_endpoint():

    boto_session = Mock("boto_session")
    resource_mock = Mock("resource")
    client_mock = Mock("client")
    boto_attrs = {"region_name": "us-east-1"}
    boto_session.configure_mock(**boto_attrs)
    boto_session.resource = Mock(name="resource", return_value=resource_mock)
    boto_session.client = Mock(name="client", return_value=client_mock)

    local_session = sagemaker.local.local_session.LocalSession(
        boto_session=boto_session, s3_endpoint_url=ENDPOINT_URL
    )

    local_session.default_bucket = Mock(name="default_bucket", return_value=BUCKET_NAME)
    return local_session


def test_local_session_with_custom_s3_endpoint_url(sagemaker_session_custom_endpoint):

    boto_session = sagemaker_session_custom_endpoint.boto_session

    boto_session.client.assert_called_with("s3", endpoint_url=ENDPOINT_URL)
    boto_session.resource.assert_called_with("s3", endpoint_url=ENDPOINT_URL)

    assert sagemaker_session_custom_endpoint.s3_client is not None
    assert sagemaker_session_custom_endpoint.s3_resource is not None


def test_local_session_download_with_custom_s3_endpoint_url(sagemaker_session_custom_endpoint):

    DOWNLOAD_DATA_TESTS_FILES_DIR = os.path.join(DATA_DIR, "download_data_tests")
    sagemaker_session_custom_endpoint.s3_client.list_objects_v2 = Mock(
        name="list_objects_v2", return_value=LS_FILES
    )
    sagemaker_session_custom_endpoint.s3_client.download_file = Mock(name="download_file")

    sagemaker_session_custom_endpoint.download_data(
        DOWNLOAD_DATA_TESTS_FILES_DIR, BUCKET_NAME, key_prefix="/data/test.csv"
    )

    sagemaker_session_custom_endpoint.s3_client.download_file.assert_called_with(
        Bucket=BUCKET_NAME,
        Key="/data/test.csv",
        Filename="{}/{}".format(DOWNLOAD_DATA_TESTS_FILES_DIR, "test.csv"),
        ExtraArgs=None,
    )


@patch("sagemaker.local.local_session.get_docker_host")
@patch("urllib3.PoolManager.request")
def test_invoke_local_endpoint_with_remote_docker_host(
    m_request,
    m_get_docker_host,
):
    m_get_docker_host.return_value = "some_host"
    Body = "Body".encode("utf-8")
    url = "http://%s:%d/invocations" % ("some_host", 8080)
    sagemaker.local.local_session.LocalSagemakerRuntimeClient().invoke_endpoint(
        Body, "local_endpoint"
    )
    m_request.assert_called_with("POST", url, body=Body, preload_content=False, headers={})


def test_create_describe_update_pipeline():
    parameter = ParameterString("MyStr", default_value="test")
    pipeline = Pipeline(
        name="MyPipeline",
        parameters=[parameter],
        steps=[CustomStep(name="MyStep", input_data=parameter)],
        sagemaker_session=LocalSession(),
    )
    definition = pipeline.definition()
    pipeline.create("dummy-role", "pipeline-description")

    pipeline_describe_response1 = pipeline.describe()
    assert pipeline_describe_response1["PipelineArn"] == "MyPipeline"
    assert pipeline_describe_response1["PipelineDefinition"] == definition
    assert pipeline_describe_response1["PipelineDescription"] == "pipeline-description"

    pipeline = Pipeline(
        name="MyPipeline",
        parameters=[parameter],
        steps=[CustomStep(name="MyStepUpdated", input_data=parameter)],
        sagemaker_session=LocalSession(),
    )
    updated_definition = pipeline.definition()
    pipeline.update("dummy-role", "pipeline-description-2")
    pipeline_describe_response2 = pipeline.describe()
    assert pipeline_describe_response2["PipelineDescription"] == "pipeline-description-2"
    assert pipeline_describe_response2["PipelineDefinition"] == updated_definition
    assert (
        pipeline_describe_response2["CreationTime"]
        != pipeline_describe_response2["LastModifiedTime"]
    )


@patch("sagemaker.local.pipeline.LocalPipelineExecutor.execute")
def test_start_pipeline(mock_local_pipeline_executor):
    parameter = ParameterString("MyStr", default_value="test")
    pipeline = Pipeline(
        name="MyPipeline",
        parameters=[parameter],
        steps=[CustomStep(name="MyStep", input_data=parameter)],
        sagemaker_session=LocalSession(),
    )
    pipeline.create("dummy-role", "pipeline-description")
    mock_local_pipeline_executor.return_value = _LocalPipelineExecution("execution-id", pipeline)

    pipeline_execution = pipeline.start()
    pipeline_execution_describe_response = pipeline_execution.describe()
    assert pipeline_execution_describe_response["PipelineArn"] == "MyPipeline"
    assert pipeline_execution_describe_response["PipelineExecutionArn"] == "execution-id"
    assert pipeline_execution_describe_response["CreationTime"] is not None


def test_update_undefined_pipeline():
    session = LocalSession()
    parameter = ParameterString("MyStr", default_value="test")
    pipeline = Pipeline(
        name="UndefinedPipeline",
        parameters=[parameter],
        steps=[CustomStep(name="MyStep", input_data=parameter)],
        sagemaker_session=session,
    )

    with pytest.raises(ClientError) as e:
        session.sagemaker_client.update_pipeline(pipeline, "some_description")
    assert "Pipeline {} does not exist".format(pipeline.name) in str(e.value)


def test_describe_undefined_pipeline():
    with pytest.raises(ClientError) as e:
        LocalSession().sagemaker_client.describe_pipeline("UndefinedPipeline")
    assert "Pipeline UndefinedPipeline does not exist" in str(e.value)


def test_start_undefined_pipeline():
    with pytest.raises(ClientError) as e:
        LocalSession().sagemaker_client.start_pipeline_execution("UndefinedPipeline")
    assert "Pipeline UndefinedPipeline does not exist" in str(e.value)
