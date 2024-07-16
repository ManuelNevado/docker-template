class MarkupError(Exception):
    """Exception raised for errors when markup Action

    Attributes:
        mark -- mark
        message -- explanation of the error
    """

    def __init__(self, mark, message="Unexpected error ocurred"):
        self.mark = mark
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'ERROR: {self.message} with the mark {self.mark}.'
