from app.contacts.domain.contact_message import contact_message


def test_message_names_the_company_and_the_job() -> None:
    text = contact_message(
        company_name="Synthetic Company",
        job_title="Synthetic Role",
        message="We would like to talk.",
    )

    assert text == (
        'Synthetic Company entrou em contato sobre a vaga "Synthetic Role":\n\n'
        "We would like to talk."
    )
