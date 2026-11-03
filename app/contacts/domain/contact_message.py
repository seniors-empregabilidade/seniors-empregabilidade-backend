def contact_message(*, company_name: str, job_title: str, message: str) -> str:
    """Text the professional reads in the notification center and the e-mail.

    It is built only from what the company chose to share: its public name, the
    job title and its own message. Nothing about the professional (name, CPF,
    address, phone, e-mail) is read into it.
    """
    return f'{company_name} entrou em contato sobre a vaga "{job_title}":\n\n{message}'
