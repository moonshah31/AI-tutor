
import pytest
from bson import ObjectId

from app.services.retrieval_parameter_sweep import (
    run_parameter_sweep,
)


@pytest.mark.asyncio
async def test_parameter_sweep_rejects_empty_thresholds():
    with pytest.raises(ValueError, match="At least one threshold"):
        await run_parameter_sweep(
            database=None,
            user_id=ObjectId(),
            cases=[],
            thresholds=[],
            weights=[0.5],
        )


@pytest.mark.asyncio
async def test_parameter_sweep_rejects_empty_weights():
    with pytest.raises(ValueError, match="At least one weight"):
        await run_parameter_sweep(
            database=None,
            user_id=ObjectId(),
            cases=[],
            thresholds=[0.35],
            weights=[],
        )
