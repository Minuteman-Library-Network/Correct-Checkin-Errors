# Correct Checkin Errors
 Script identifies the subset of items that were not checked in as expected, due to a patron record being left open in another session.
 The identifiable items are cases in which an item appears to be simultaneously checked out and in transit to a different location.
 In these instances, the transit information appears to be correct and the item should be removed from the patron record.
 The script will check in the item again using the Sierra API, which clears the discrepancy, and logs the item information for future reference.
