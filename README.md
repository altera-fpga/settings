# settings
Contains configuration files and scripts for the altera-fpga Github site

## Flow for Adding Example Designs into Quartus
1. Create a new pull request to add your GitHub repository to [predefined_url.json](https://github.com/altera-fpga/settings/blob/main/predefined_url.json).
2. Once the pull request is approved, an automated job will scan your GitHub repository and populate the example designs in [catalog/list.json](https://github.com/altera-fpga/settings/blob/main/catalog/list.json).
   - Note: DO NOT manually modify the catalog/list.json
3. A new pull request for the catalog/list.json changes will then be created automatically. Once it is approved, your example design will be listed in Quartus.
