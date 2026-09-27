from app.models.payment import PaymentAttempt


def test_attempt_model_declares_single_active_attempt_index():
    index = next(index for index in PaymentAttempt.__table__.indexes
                 if index.name == "uq_attempt_one_active_per_payment")
    assert index.unique is True
    assert "status IN ('INITIATED', 'PENDING', 'UNKNOWN')" in str(index.dialect_options["postgresql"]["where"])
