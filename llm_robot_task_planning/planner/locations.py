import yaml

class LocationManager:
    def __init__(self, locations_yaml_path: str):
        with open(locations_yaml_path, 'r') as f:
            self.locations = yaml.safe_load(f)['locations']

    def get_location(self, name: str) -> dict | None:
        return self.locations.get(name.lower())

    def get_all_locations(self) -> dict:
        return self.locations
