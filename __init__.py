import random
import logging
from collections import defaultdict
from typing import Dict, Union, ClassVar, Any, Mapping
from BaseClasses import MultiWorld, Item, ItemClassification, Tutorial
from worlds.AutoWorld import World, CollectionState, WebWorld
from worlds.sly1.Items import item_table, create_itempool, create_item, event_item_pairs, sly_episodes, sly_items, bottles, junk_items, ep_fix, lvl_to_ep
from worlds.sly1.Locations import (get_location_names, get_total_locations,
                                   did_avoid_early_bk, generate_bottle_locations,
                                   generate_minigame_locations, generate_key_caches,
                                   lvl_names, turrets, races, murray_dangers, minigames)
from worlds.sly1.Options import Sly1Options
from worlds.sly1.Regions import create_regions
from worlds.sly1.Types import Sly1Item, EpisodeType, episode_type_to_name, episode_type_to_shortened_name
from worlds.sly1.Rules import set_rules
from worlds.LauncherComponents import (
    Component,
    Type,
    components,
    launch_subprocess,
    icon_paths,
)
from Options import OptionError
import settings

def run_client():
    from worlds.sly1.Sly1Client import launch_client
    launch_subprocess(launch_client, name="Sly1Client")

#icon_paths["sly1_ico"] = f"ap:{__name__}/icon.png"
components.append(
    Component("Sly 1 Client", func=run_client, component_type=Type.CLIENT)
)

def setup_item_groups(items) -> dict[str, set]:
    # not quite as ugly as location groups (but still ugly). Would similarly be easier to deal with if item names were
    #   formatted to allow for easier retrieval of level and/or episode names. Will try that after committing/pushing this
    item_groups = defaultdict(set)
    for name in items:
        if "Progressive" in name:
            item_groups["Moves (Progressive)"].add(name)  # progressive moves
            item_groups["Moves (All)"].add(name)  # all moves
        if name in ["Coin Magnet", "Mine", "Fast", "Decoy", "Hacking"]:
            item_groups["Moves (Non-Progressive)"].add(name)  # non-progressive moves
            item_groups["Moves (All)"].add(name)  # all moves
        if name in ["Charm", "1-Up"]:
            item_groups["All Filler"].add(name)  # all filler
        if name in ["Ice Physics Trap", "Speed Change Trap", "Ball Trap", "Invisibility Trap"]:
            item_groups["All Traps"].add(name)  # all traps

        # Bottles/blueprints/keys/episode access items need episode information. Problem: access items spell out episode
        #   names while bottles/blueprints/keys don't. special case time :) have to convert episode name to its abbreviation
        for ep in ep_fix:  # check all episodes
            if name == ep:  # find which one
                item_groups["All Episode Access Items"].add(name)  # all episode access
                item_groups[f"{ep_fix[ep]} (All)"].add(name)  # individual episode (All) groups
                break

        if "Bottle" in name or "Blueprint" in name or "Key" in name:  # these 3 have same episode name format
            for lvl in lvl_to_ep:  # cycle through all levels
                if lvl in name:  # find which episode
                    episode = lvl_to_ep[lvl]
                    break

            # generalizing as a loop to cut out some repetitive lines
            for group in ["Bottle", "Blueprint", "Key"]:
                if group in name:
                    item_groups[f"All {group}s"].add(name)  # all bottles, all blueprints, all keys
                    item_groups[f"{episode} (All)"].add(name)  # ToT all, SSE all, VV all, FitS all
                    if "Bottle" in name:
                        item_groups[f"{episode} Bottles"].add(name)  # ToT bottles, SSE bottles, VV bottles, FitS bottles
    return item_groups

def setup_location_groups(locations) -> dict[str, set]:
    location_groups = defaultdict(set)
    location_groups["All Bosses"] = {"Eye of the Storm", "Last Call", "Deadly Dance", "Flame Fu!"}

    # My 2 CS degrees are screaming at me for this O(n^4) mess...I am in agony
    # I don't think this can be majorly improved without significantly cutting back on groups or adjusting location name
    #   format to "Stealthy Approach: Key" for a programmatically-easier time retrieving level names.
    # Without that, there's basically no avoiding layers of loops going over locations -> episodes -> levels -> types of level locations
    # Getting even this form working required a rename of minigame level caches to be "Minigame Cache" instead of just "Cache"
    #   because I couldn't get a logically-sound approach working without doing so.
    # Will probably make a version with modified location name formatting next to see if it's justified.
    for name in locations:  # all locations
        for episode in lvl_names:  # needed for episode-based groups
            lvls = lvl_names[episode]
            for lvl in lvls:  # needed for level-based groups
                if lvl in name:  # find which level this location belongs to
                    if lvl not in ["Eye of the Storm", "Last Call", "Deadly Dance", "Flame Fu!"] and lvl not in minigames:
                        location_groups[f"{lvl} (All)"].add(name)  # all in each level
                    location_groups[f"{episode} (All)"].add(name)  # all level matches in name -> part of current episode
                    if any(thing in name for thing in murray_dangers):
                        location_groups["All Murray Danger Levels"].add(name)  # murray danger levels
                    if any(thing in name for thing in races):
                        location_groups["All Race Levels"].add(name)  # race levels
                    if any(thing in name for thing in turrets):
                        location_groups["All Turret Levels"].add(name)  # turret levels
                    if lvl not in minigames:
                        location_groups["All Platforming Levels"].add(name)  # platforming levels

                    for group in ["Bottle", "Key", "Minigame Cache", "Vault", "Hourglass"]:  # not strictly needed, but generalizing this into a loop cuts out some repetitive lines
                        if group in name:  # find which type of location this is (Bottle, Cache, etc.)
                            # could remove some slight repetitiveness here, but I really just do not care at this point, it works
                            if "Vault" in name:
                                location_groups[f"{episode} Vaults"].add(name)  # episode vaults
                                location_groups["All Vaults"].add(name)  # all vaults

                            if "Hourglass" in name:
                                location_groups[f"{episode} Hourglasses"].add(name)  # episode hourglasses
                                location_groups["All Hourglasses"].add(name)  # all hourglasses

                            if "Bottle" in name or "Key" in name or "Minigame Cache" in name:
                                location_groups[f"{episode} {group}s"].add(name)  # per-episode bottles/keys/minigame caches
                                location_groups[f"All {group}s"].add(name)  # all bottles/keys/minigame caches

                                # English words aren't descriptive enough to capture how long it took to get this part working
                                if "Key" in name and lvl in minigames:
                                    continue  # no individual level key groups for minigame keys
                                else:
                                    location_groups[f"{lvl} {group}s"].add(name)  # per-level bottles/keys/minigame caches
    return location_groups

class Sly1Web(WebWorld):
    theme = "ocean"
    tutorials = [Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Sly Cooper and the Thievius Raccoonus for Archipelago. "
        "This guide covers single-player, multiworld, and related software.",
        "English",
        "setup_en.md",
        "setup/en",
        ["Nep"]
    )]

class Sly1Settings(settings.Group):
    class AutoFillLocations(settings.Bool):
        """Adds "Key Cache" locations if items outnumber locations, preventing errors.
        It is strongly recommended you keep this enabled unless you know what you're doing!"""
        description = "Sly 1 Auto Fill Locations"

    auto_fill_locations: Union[AutoFillLocations, bool] = True

class Sly1World(World):
    """
    Sly Cooper and the Thievius Raccoonus is a action-stealth game set in a cartoony cel-shaded world.
    Avenge your father and take back the pages of the Thievius Raccoonus from the Fiendish Five!
    """

    game = "Sly Cooper and the Thievius Raccoonus"
    item_name_to_id = {name: data.ap_code for name, data in item_table.items()}
    location_name_to_id = get_location_names()
    options_dataclass = Sly1Options
    options = Sly1Options
    web = Sly1Web()
    settings: ClassVar[Sly1Settings]

    # set up item and location groups
    item_name_groups = setup_item_groups(item_name_to_id)
    location_name_groups = setup_location_groups(location_name_to_id)

    # this is how we tell the Universal Tracker we want to use re_gen_passthrough
    @staticmethod
    def interpret_slot_data(slot_data: Dict[str, Any]) -> Dict[str, Any]:
        return slot_data

    # and this is how we tell Universal Tracker we don't need the yaml
    ut_can_gen_without_yaml = True

    def __init__(self, multiworld: MultiWorld, player: int):
        super().__init__(multiworld, player)
        self.generated_key_caches = 0

    def generate_early(self) -> None:
        # implement .yaml-less Universal Tracker support
        if hasattr(self.multiworld, "generation_is_fake"):
            if hasattr(self.multiworld, "re_gen_passthrough"):
                # I'm doing getattr purely so pylance stops being mad at me
                re_gen_passthrough = getattr(self.multiworld, "re_gen_passthrough")

                if "Sly Cooper and the Thievius Raccoonus" in re_gen_passthrough:
                    slot_data = re_gen_passthrough["Sly Cooper and the Thievius Raccoonus"]
                    self.options.UnlockClockwerk.value = slot_data["UnlockClockwerk"]
                    self.options.FastClockwerk.value = slot_data["FastClockwerk"]
                    self.options.RequiredBosses.value = slot_data["RequiredBosses"]
                    self.options.MaxPages.value = slot_data["MaxPages"]
                    self.options.RequiredPages.value = slot_data["RequiredPages"]
                    self.options.StartingEpisode.value = slot_data["StartingEpisode"]
                    self.options.IncludeHourglasses.value = slot_data["IncludeHourglasses"]
                    self.options.HourglassesRequireRoll.value = slot_data["HourglassesRequireRoll"]
                    self.options.AvoidEarlyBK.value = slot_data["AvoidEarlyBK"]
                    self.options.ExcludeMinigames.value = slot_data["ExcludeMinigames"]
                    self.options.MinigameCaches.value = slot_data["MinigameCaches"]
                    self.options.LocationCluesanityBundleSize.value = slot_data["LocationCluesanityBundleSize"]
                    self.options.ItemCluesanityBundleSize.value = slot_data["ItemCluesanityBundleSize"]
                    self.options.CutsceneSkip.value = slot_data["CutsceneSkip"]
                    self.options.TrapChance.value = slot_data["TrapChance"]
                    self.options.IcePhysicsTrapWeight.value = slot_data["IcePhysicsTrapWeight"]
                    self.options.SpeedChangeTrapWeight.value = slot_data["SpeedChangeTrapWeight"]
                    self.options.InvisibilityTrapWeight.value = slot_data["InvisibilityTrapWeight"]
                    self.options.BallTrapWeight.value = slot_data["BallTrapWeight"]
            return

        starting_episode = EpisodeType(self.options.StartingEpisode)
        starting_episode_long = episode_type_to_name[starting_episode]
        starting_episode_short = episode_type_to_shortened_name[starting_episode]

        # Starting Episode - please clean this up oml
        if starting_episode_long == "All":
            for episode in sly_episodes.keys():
                self.multiworld.push_precollected(self.create_item(episode))
        else:
            self.multiworld.push_precollected(self.create_item(starting_episode_long))

        # Avoid Early BK
        if did_avoid_early_bk(self):
            if starting_episode_long == "All":
                starting_episode_short = episode_type_to_shortened_name[EpisodeType(random.randrange(1, 4))]
                self.random_episode = starting_episode_short
            self.multiworld.push_precollected(self.create_item(f'{starting_episode_short} Key'))

    def create_regions(self):
        create_regions(self)

        if self.options.LocationCluesanityBundleSize.value > 0:
            generate_bottle_locations(self, self.options.LocationCluesanityBundleSize.value)

        if self.options.LocationCluesanityBundleSize.value == 0 and self.options.ItemCluesanityBundleSize.value > 0:
            logging.warning(
                f"{self.player}: Cannot have item bundles without location bundles. Setting location bundle size to item bundle size.")
            self.options.LocationCluesanityBundleSize.value = self.options.ItemCluesanityBundleSize.value
            generate_bottle_locations(self, self.options.LocationCluesanityBundleSize.value)
        
        generate_minigame_locations(self, self.options.MinigameCaches.value)

    def create_items(self):
        itempool = create_itempool(self)
        self.multiworld.itempool.extend(itempool)

        for event, item in event_item_pairs.items():
            event_item = Sly1Item(item, ItemClassification.progression_skip_balancing, None, self.player)
            self.multiworld.get_location(event, self.player).place_locked_item(event_item)

        if Sly1World.settings.auto_fill_locations:
            total_locations = get_total_locations(self)
            total_items = sum(1 for item in self.multiworld.itempool if item.player == self.player) + len(
                event_item_pairs) + 1
            deficit = total_items - total_locations
            generate_key_caches(self, deficit)
            self.generated_key_caches = max(0, deficit)
        else:
            location_count = len(self.multiworld.get_unfilled_locations(self.player))
            item_count = len(itempool)
            if location_count - item_count < 0:
                self.handle_not_enough_locations(item_count - location_count)

    def handle_not_enough_locations(self, count):
        """Check the available location and items counts, raise OptionErrors to warn the player of too few locations"""
        option_list: list[str] = []
        if self.options.LocationCluesanityBundleSize == 0:
            option_list.append("Location Cluesanity Bundle Size")
        if self.options.MinigameCaches == 0:
            option_list.append("Minigame Caches")
        if not option_list:
            option_list: str = "dunno"  # ¯\_(''/)_/¯
        message = f"Not enough location options enabled! {count} items have nowhere to be placed."
        message += f"Consider adjusting some of the following options: {option_list}"
        raise OptionError(message)
    set_rules = set_rules

    def create_item(self, name: str) -> Item:
        return create_item(self, name)

    def get_options_as_dict(self) -> Dict[str, Any]:
        return self.options.as_dict(
            "UnlockClockwerk",
            "RequiredBosses",
            "MaxPages",
            "RequiredPages",
            "FastClockwerk",
            "StartingEpisode",
            "IncludeHourglasses",
            "HourglassesRequireRoll",
            "AvoidEarlyBK",
            "LocationCluesanityBundleSize",
            "ItemCluesanityBundleSize",
            "CutsceneSkip",
            "ExcludeMinigames",
            "MinigameCaches",
            "TrapChance",
            "IcePhysicsTrapWeight",
            "SpeedChangeTrapWeight",
            "InvisibilityTrapWeight",
            "BallTrapWeight",
        )

    def fill_slot_data(self) ->Mapping[str, object]:
        return {
            "UnlockClockwerk": self.options.UnlockClockwerk.value,
            "RequiredBosses": self.options.RequiredBosses.value,
            "MaxPages": self.options.MaxPages.value,
            "RequiredPages": self.options.RequiredPages.value,
            "FastClockwerk": self.options.FastClockwerk.value,
            "StartingEpisode": self.options.StartingEpisode.value,
            "IncludeHourglasses": self.options.IncludeHourglasses.value,
            "HourglassesRequireRoll": self.options.HourglassesRequireRoll.value,
            "AvoidEarlyBK": self.options.AvoidEarlyBK.value,
            "LocationCluesanityBundleSize": self.options.LocationCluesanityBundleSize.value,
            "ItemCluesanityBundleSize": self.options.ItemCluesanityBundleSize.value,
            "CutsceneSkip": self.options.CutsceneSkip.value,
            "ExcludeMinigames": self.options.ExcludeMinigames.value,
            "MinigameCaches": self.options.MinigameCaches.value,
            "TrapChance": self.options.TrapChance.value,
            "IcePhysicsTrapWeight": self.options.IcePhysicsTrapWeight.value,
            "SpeedChangeTrapWeight": self.options.SpeedChangeTrapWeight.value,
            "InvisibilityTrapWeight": self.options.InvisibilityTrapWeight.value,
            "BallTrapWeight": self.options.BallTrapWeight.value,
            "Seed": self.multiworld.seed_name,
        }

    def collect(self, state: "CollectionState", item: "Item") -> bool:
        return super().collect(state, item)
    
    def remove(self, state: "CollectionState", item: "Item") -> bool:
        return super().remove(state, item)