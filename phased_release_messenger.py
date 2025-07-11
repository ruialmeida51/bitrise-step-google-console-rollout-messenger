import subprocess
import sys
import httplib2
import requests
from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from oauth2client.client import AccessTokenRefreshError


def get_edit_id(service, package_name):
    """
    Begins an edit transaction and gets the editId for the specified package name.

    Args:
        service: Authorized Google Play Developer API service instance.
        package_name (str): The application package name.

    Returns:
        str: The edit ID for the current transaction.
    """
    edits = service.edits().insert(packageName=package_name).execute()
    return edits['id']


def get_info_for_track(service, edit_id, package_name, track):
    """
    Retrieves information for a given track: status, rollout percentage, release notes, version codes, etc.

    Args:
        service: Authorized Google Play Developer API service instance.
        edit_id (str): The ID of the current edit session.
        package_name (str): The application package name.
        track (str): The track to query (e.g. 'internal', 'production').

    Returns:
        dict: The track release metadata.
    """
    return service.edits().tracks().get(
        editId=edit_id,
        packageName=package_name,
        track=track
    ).execute()


def parse_rollout_steps(rollout_steps_raw):
    """
    Parses and validates a rollout step string (e.g., '1,20,50,100').

    Validates that:
    - All values are comma-separated integers.
    - Each value is between 0 and 100.
    - A value must always be bigger than the previous one.

    Converts valid percentages into float fractions for the Play Console API (e.g., 20 -> 0.2).

    Args:
        rollout_steps_raw (str): Comma-separated string of rollout steps.

    Returns:
        List[float]: A list of rollout fractions (e.g., [0.01, 0.2, 0.5, 1.0]).

    Raises:
        SystemExit: If the format is invalid or constraints are violated.
    """
    try:
        steps = [int(s.strip()) for s in rollout_steps_raw.split(",")]
    except ValueError:
        raise SystemExit("💥 Rollout steps must be comma-separated numbers only (e.g., 1,20,50,100)")

    if any(step < 0 or step > 100 for step in steps):
        raise SystemExit("💥 All rollout steps must be between 0 and 100.")

    if any(steps[i] >= steps[i + 1] for i in range(len(steps) - 1)):
        raise SystemExit("💥 Each rollout step must be strictly greater than the previous (e.g., 1,20,50,100).")

    return [step / 100.0 for step in steps]


def send_post(url, payload):
    response = requests.post(
        url=url,
        json=payload
    )

    if response.status_code == 200 or response.status_code == 202:
        print("✅ Message sent:", response.json())
    else:
        print("❌ Something went wrong whilst sending a response:", response.status_code, response.text)


def main():
    track = sys.argv[1]
    rollout_increase_steps = sys.argv[2]
    package_name = sys.argv[3]
    webhook_url = sys.argv[4]
    service_credentials_file = sys.argv[5]

    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        service_credentials_file,
        scopes='https://www.googleapis.com/auth/androidpublisher'
    )

    http = httplib2.Http()
    http = credentials.authorize(http)

    service = build('androidpublisher', 'v3', http=http)

    try:
        edit_id = get_edit_id(
            service=service,
            package_name=package_name
        )

        track_info = get_info_for_track(
            service=service,
            edit_id=edit_id,
            package_name=package_name,
            track=track
        )

        if 'releases' not in track_info or not track_info['releases']:
            print("⚠️ Track has no releases. Skipping messages.")
            sys.exit(0)

        for release in track_info['releases']:
            # Get the release status
            release_status = release['status']
            print("📝 Status is: " + release_status)

            # If it's completed, nothing to do. Carry on.
            if release_status == "completed":
                print("✅ Release is completed. No messaging needed.")
                sys.exit(0)

            # Once again, if it's halted, nothing to do. Carry on.
            if release_status == "halted":
                print("⚠️ Release was halted. Skipping messaging.")
                sys.exit(0)

            print("🚧 Release is in progress, continuing update.")

            # Parse our rollout steps.
            rollout_steps = parse_rollout_steps(rollout_increase_steps)
            print("🪜 Rollout steps are: ", rollout_steps)

            current_rollout_percentage = release['userFraction']
            new_rollout_percentage = None

            # Update our rollout step to the next increment based on the rollout percentage
            for step in rollout_steps:
                if step > current_rollout_percentage:
                    new_rollout_percentage = step
                    break

            if new_rollout_percentage is None:
                print("ℹ️ No higher rollout step found. Already at or above maximum configured value.")

            print(
                f"📝 Attempting to message about increasing the rollout from {current_rollout_percentage} to: {new_rollout_percentage}")

            # Made with:
            # https://adaptivecards.io/designer/
            send_post(
                url=webhook_url,
                payload={
                    "type": "message",
                    "attachments": [
                        {
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "content": {
                                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                                "type": "AdaptiveCard",
                                "version": "1.2",
                                "body": [
                                    {
                                        "type": "TextBlock",
                                        "size": "Medium",
                                        "weight": "Bolder",
                                        "text": "Bitrise"
                                    },
                                    {
                                        "type": "ColumnSet",
                                        "columns": [
                                            {
                                                "type": "Column",
                                                "items": [
                                                    {
                                                        "type": "Image",
                                                        "style": "Person",
                                                        "url": "https://classic.battle.net/war3/images/orc/units/portraits/peon.gif",
                                                        "altText": "Worker Peon",
                                                        "size": "Small"
                                                    }
                                                ],
                                                "width": "auto"
                                            },
                                            {
                                                "type": "Column",
                                                "items": [
                                                    {
                                                        "type": "TextBlock",
                                                        "weight": "Bolder",
                                                        "text": "Google Console Rollout Updater",
                                                        "wrap": "true"
                                                    }
                                                ],
                                                "width": "stretch",
                                                "verticalContentAlignment": "Center"
                                            }
                                        ]
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": "The current staged release will automatically increase from " +
                                                str(current_rollout_percentage * 100) +
                                                "% to " +
                                                str(new_rollout_percentage * 100) +
                                                "% at 11 AM today.",
                                        "wrap": "true"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": "The halt buttons require your KF Google account to be the primary (first) account signed in. If it isn’t, please sign out of all accounts and then sign back in starting with the KF account you want to use.",
                                        "wrap": "true"
                                    },
                                ],
                                "actions": [
                                    {
                                        "type": "Action.OpenUrl",
                                        "title": "BQ: Click here to halt",
                                        "url": "https://play.google.com/console/u/0/developers/6065722340822178479/app/4975443815265185899/tracks/production?tab=releases",
                                        "style": "destructive",
                                        "iconUrl": "https://wow.zamimg.com/uploads/screenshots/normal/287195-avatar-of-ragnaros.jpg"
                                    },
                                    {
                                        "type": "Action.OpenUrl",
                                        "title": "TP: Click here to halt",
                                        "url": "https://play.google.com/console/u/0/developers/6065722340822178479/app/4975349855517202999/tracks/production?tab=releases",
                                        "style": "destructive",
                                        "iconUrl": "https://www.meme-arsenal.com/memes/68c7b0ca4d7c9c773ab5bc013c3fa170.jpg"
                                    },
                                ]
                            }
                        }
                    ]
                }
            )

    except AccessTokenRefreshError:
        raise SystemExit(
            '💥 The credentials have been revoked or expired, please re-run the application to re-authorize'
        )


if __name__ == '__main__':
    main()
