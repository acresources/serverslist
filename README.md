# AC Servers
This is central repository for AC emulated servers, managed by the community.  
To add or update your server, please submit a pull request.

***
## Disclaimer
**This project is for educational and non-commercial purposes only.**
- Asheron's Call was a registered trademark of Turbine, Inc. and WB Games Inc which has since expired.
- ACResources is not associated or affiliated in any way with Turbine, Inc. or WB Games Inc.
***

## Server Template
* [Sample](https://raw.githubusercontent.com/acresources/serverslist/master/Template.xml)

## Server Template Fields
* <id\> This is the unique guid of your server. You can generate one here: https://www.guidgenerator.com.
* <name\> The name of your server.
* <description\> A brief statement describing your server (Optional)
* <emu\> Valid values are: ACE, GDL
* <server_host\> Your servers address, for example, myserver.mydomain.com
* <server_port\> Your servers port. Default is 9000
* <type\> Valid values are: PvE, PvP (Optional)
* <status\> Valid values are: Experimental, Development, Stable (Optional)
* <website_url\> (Optional)
* <discord_url\> (Optional)

## FAQ

#### Can I change my server id?
* Once a server is submitted, it's id must not change.
* If you decomission your server and start up a new server, even if your new server reuses the same name, you should submit a new server to the list using a new id.
* Your servers lifetime should be represented by the Shard database that stores your world.
* A new Shard should be considered a new server.

#### Can I change my server name?
* Yes, you can change your servers name.
* Changing your servers name can break many plugins like VTank and Mag-Tools. Your users may need to reconfigure their plugins after the name change.

#### Who can submit changes to my server?
* Only the original pull request author that submitted the server should provide updates.
* If you need to update a server and no longer have access to your original github account, please submit the PR with a comment and someone will reach out to you.

#### Who can add a server to the list?
* Anyone

#### Who approves pull requests?
* There are several community members that can accept pull requests.

## Other Resources
* [ACEmulator](https://github.com/ACEmulator/ACE)
* [GDLEnhanced](https://gitlab.com/Scribble/gdlenhanced)
