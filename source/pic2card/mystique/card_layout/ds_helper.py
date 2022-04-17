"""Module responsible for all the utilities and template classes needed for
the layout generation"""
# pylint: disable=relative-beyond-top-level

from typing import List, Tuple, Dict, Union

import pandas as pd

from .objects_group import ChoicesetGrouping
import copy

class DsHelper:
    """
    Base class for layout ds utilities and template handling.
    - handles all utility functions needed for the layout generation
    """

    CONTAINERS = ["columnset", "imageset", "column",  'choiceset', 'factset' ]
    MERGING_CONTAINERS_LIST = [ 'choiceset', 'factset']
    def __init__(self):

        self.serialized_layout = []
        self.ds_template = DsDesignTemplate()

    def merge_properties(
        self,
        properties: List[Dict],
        design_object: List[Dict],
        container_details_object: object,
    ) -> None:
        """
        Merges the design objects with properties with the appropriate layout
        structure with the help of the uuid.
        @param properties: design objects with properties
        @param design_object: layout data structure
        @param container_details_object: ContainerDetailsTemplate object
        """
        if (
            isinstance(design_object, dict)
            and design_object.get("object", "") not in DsHelper.CONTAINERS
        ):
            extracted_properties = [
                prop
                for prop in properties
                if prop.get("uuid", "") == design_object.get("uuid")
            ][0]
            extracted_properties.pop("coordinates")
            design_object.update(extracted_properties)

        elif isinstance(design_object, list):
            for design_obj in design_object:
                self.merge_properties(
                    properties, design_obj, container_details_object
                )
        else:
            container_details_template_object = getattr(
                container_details_object, design_object.get("object", "")
            )
            self.merge_properties(
                properties,
                container_details_template_object(design_object),
                container_details_object,
            )

    def export_debug_string(
        self,
        serialized_layout: List,
        design_object: Union[List, Dict],
        card_layout: List[Dict],
        indentation=None,
    ) -> None:
        """
        Recursively generates the debug layout structure string.
        @param serialized_layout: debug layout structure string
        @param design_object: design objects from the layout structure
        @param indentation: indentation
        @param card_layout: generated layout structure
        """
        if (
            isinstance(design_object, dict)
            and design_object.get("object", "") not in DsHelper.CONTAINERS
        ):
            design_class = design_object.get("class", "")
            if design_object in card_layout:
                tab_space = "\t" * 0
            else:
                tab_space = "\t" * (indentation + 1)
            serialized_layout.append(f"{tab_space}item({design_class})\n")
        elif isinstance(design_object, list):
            for design_obj in design_object:
                self.export_debug_string(
                    serialized_layout,
                    design_obj,
                    card_layout,
                    indentation=indentation,
                )
        else:
            export_serialized_layout_template = SerializedLayoutExport(
                design_object, card_layout, self
            )
            export_serialized_layout_template_object = getattr(
                export_serialized_layout_template,
                design_object.get("object", ""),
            )
            export_serialized_layout_template_object(
                serialized_layout, indentation
            )

    def build_serialized_layout_string(self, card_layout: List[Dict]) -> List:
        """
        Returns the exported adaptive card json
        @param card_layout: adaptive card body
        @return: debugging data-structure format
        """
        card_layout = [
            value
            for _, value in sorted(
                zip(
                    list(zip(*pd.DataFrame(card_layout)["coordinates"]))[1],
                    card_layout,
                ),
                key=lambda value: value[0],
            )
        ]

        self.export_debug_string(
            self.serialized_layout, card_layout, card_layout, indentation=0
        )
        return self.serialized_layout

    def add_element_to_ds(
        self, element_type: str, card_layout: List, element=None, coords=None
    ) -> None:
        """
        Adds the design element structure to the layout data structure.
        @param element_type: type of passed design element [ individual /
                             any container]
        @param card_layout: layout structure where the design element
                                 has to be added
        @param element: design element to be added
        """
        element_structure_object = getattr(self.ds_template, element_type)
        element_structre = element_structure_object(element)
        if element_structre not in card_layout:
            card_layout.append(element_structure_object(element))
            if coords:
                card_layout[-1].update({"coordinates": coords})

    # pylint: disable=no-self-use
    def build_container_coordinates(self, coordinates: List) -> Tuple:
        """
        Returns the column set or column coordinates by taking min(x minimum and
        y minimum) and max(x maximum and y maximum) of the respective
        container's element's coordinates.

        @param coordinates: container's list of coordinates
        @return: coordinates of the respective container
        """
        x_minimums = [c[0] for c in coordinates]
        y_minimums = [c[1] for c in coordinates]
        x_maximums = [c[2] for c in coordinates]
        y_maximums = [c[3] for c in coordinates]
        return (
            min(x_minimums),
            min(y_minimums),
            max(x_maximums),
            max(y_maximums),
        )


class SerializedLayoutExport:
    """
    This class is responsible for calling the appropriate debug templates
    for the container structure.
    """

    def __init__(self, design_object, card_layout, export_object):
        self.design_object = design_object
        self.card_layout = card_layout
        self.export_object = export_object

    def columnset(self, serialized_layout_string, indentation) -> None:
        """
        Returns the debugging string for the column-set container @param
        serialized_layout_string: list of debugging string for the given
        design @param indentation: needed indentation for design element in
        the debugging string
        """
        if self.design_object in self.card_layout:
            tab_space = "\t" * 0
        else:
            tab_space = "\t" * (indentation + 1)
            indentation = indentation + 1
        serialized_layout_string.append(f"{tab_space}row\n")
        self.export_object.export_debug_string(
            serialized_layout_string,
            self.design_object.get("row", []),
            self.card_layout,
            indentation=indentation,
        )

    def column(self, serialized_layout_string, indentation) -> None:
        """
        Returns the debugging string for the column container @param
        serialized_layout_string: list of debugging string for the given
        design @param indentation: needed indentation for design element in
        the debugging string
        """
        if self.design_object in self.card_layout:
            tab_space = "\t" * 0
        else:
            tab_space = "\t" * (indentation + 1)
            indentation = indentation + 1
        serialized_layout_string.append(f"{tab_space}column\n")
        self.export_object.export_debug_string(
            serialized_layout_string,
            self.design_object.get("column", {}).get("items", []),
            self.card_layout,
            indentation=indentation,
        )

    def imageset(self, serialized_layout_string, indentation) -> None:
        """
        Returns the debugging string for the image-set container @param
        serialized_layout_string: list of debugging string for the given
        design @param indentation: needed indentation for design element in
        the debugging string
        """
        if self.design_object in self.card_layout:
            tab_space = "\t" * 0
        else:
            tab_space = "\t" * (indentation + 1)
            indentation = indentation + 1
        serialized_layout_string.append(f"{tab_space}imageset\n")
        self.export_object.export_debug_string(
            serialized_layout_string,
            self.design_object.get("imageset", {}).get("items", []),
            indentation=indentation,
        )

    def choiceset(self, serialized_layout_string, indentation) -> None:
        """
        Returns the debugging string for the image-set container @param
        serialized_layout_string: list of debugging string for the given
        design @param indentation: needed indentation for design element in
        the debugging string
        """
        if self.design_object in self.card_layout:
            tab_space = "\t" * 0
        else:
            tab_space = "\t" * (indentation + 1)
            indentation = indentation + 1
        serialized_layout_string.append(f"{tab_space}choiceset\n")
        self.export_object.export_debug_string(
            serialized_layout_string,
            self.design_object.get("choiceset", {}).get("items", []),
            indentation=indentation,
        )


class DsDesignTemplate:
    """
    Layout structure template for the design elements
    - Handles the template needed for the different design elements for
    the layout generation.
    """

    def item(self, design_element: Dict) -> Dict:  # pylint: disable=no-self-use
        """
        Returns the design structure for the primary card design elements
        @param: design element
        @return: design structure
        """
        return {
            "object": design_element.get("object", ""),
            "data": design_element.get("data", ""),
            "class": design_element.get("class", ""),
            "uuid": design_element.get("uuid"),
            "coordinates": design_element.get("coordinates", ()),
        }

    # pylint: disable=no-self-use, unused-argument
    def row(self, design_element: Dict) -> Dict:
        """
        Returns the design structure for the column-set container
        @param: design element
        @return: design structure
        """
        return {
            "object": "columnset",
            "row": [],
        }

    # pylint: disable=no-self-use, unused-argument
    def column(self, design_element: Dict) -> Dict:
        """
        Returns the design structure for the column of the column-set container
        @param: design element
        @return: design structure
        """
        return {"column": {"items": []}, "object": "column"}

    # pylint: disable=no-self-use, unused-argument
    def imageset(self, design_element: Dict) -> Dict:
        """
        Returns the design structure for the image-set container
        @return: design structure
        """
        return {"imageset": {"items": []}, "object": "imageset"}

    # pylint: disable=no-self-use, unused-argument
    def choiceset(self, design_element: Dict) -> Dict:
        """
        Returns the design structure for the choice-set container
        @param: design element
        @return: design structure
        """
        return {"choiceset": {"items": []}, "object": "choiceset"}

    def factset(self, design_element: Dict) -> Dict:
        """
        Returns the design structure for the choice-set container
        @param: design element
        @return: design structure
        """
        return {"factset": {"items": []}, "object": "factset"}



# pylint: disable=too-few-public-methods
class ContainerTemplate:
    """
    Class to handle different container groupings other than columnset and
    column.
    - Handles the functionalies needed for different type of container
    groupings.
    """
    def __init__(self):
        self.factset_items = []
        self.first_columnset_index = ''
        self.factset_row_index = ''
    
    def choiceset(
        self, card_layout: List[Dict], containers_group_object
    ) -> List[Dict]:
        """
        Groups and returns the layout structure with the respective choice-sets
        @param card_layout: Un-grouped layout structure.
        @param containers_group_object: ContainerGroup object
        @return: Grouped layout structure
        """
        choice_grouping = ChoicesetGrouping(self)
        condition = choice_grouping.choiceset_condition
        merging_payload = {
            "object_class": 2,
            "grouping_type": "choiceset",
            "grouping_object": choice_grouping,
            "grouping_condition": condition,
            "order_key": 1,
        }
        containers_group_object.merge_column_items(card_layout, merging_payload)
        items, _ = containers_group_object.collect_items_for_container(
            card_layout, 2
        )
        return containers_group_object.add_merged_items(
            items, card_layout, merging_payload
        )
    
    def factset(
        self, card_layout: List[Dict], containers_group_object
    ) -> List[Dict]:
        """
        Groups and returns the layout structure with the respective choice-sets
        @param card_layout: Un-grouped layout structure.
        @param containers_group_object: ContainerGroup object
        @return: Grouped layout structure
        """
        import itertools
        self.detect_factset_items(card_layout)
        self.factset_items = list(itertools.chain.from_iterable(self.factset_items))
        if len(self.factset_items)%2==0 and self.factset_items:
            card_layout = self.update_cards_layout(card_layout)
            print('update_car_layout', card_layout)
            card_layout = self.arrange_card_layout(card_layout)
            print('arrange_CAR_LAYOUT', card_layout)
        return card_layout

    def arrange_card_layout(self,card_layout):
        second_columnset_index = self.first_columnset_index+1
        new_card_layout = copy.deepcopy(card_layout)
        items_removed = 0
        for layout, index in zip(card_layout[second_columnset_index:], range(second_columnset_index, len(card_layout))):
            rows=layout.get('row', [])
            flag=0
            for row in rows:
                if row['column']['items'][0] in self.factset_items:
                    flag+=1
            if flag==2 and len(rows)==2:
                if items_removed:
                    index=index-items_removed
                new_card_layout.pop(index)
                items_removed+=1
        return new_card_layout



    def get_factset_coordinates(self, factset_items):
        for item in factset_items:
            coordinates  = item['coordinates']
            xmin,ymin, xmax, ymax = '', '', '', ''
            if not xmin and not ymin and not xmax and not ymax:
                xmin=coordinates[0]
                ymin=coordinates[1]
                xmax=coordinates[2]
                ymax=coordinates[3]
            elif coordinates[0]<xmin:
                xmin=coordinates[0]
            elif coordinates[1]<ymin:
                ymin=coordinates[1]
            elif coordinates[2]>xmax:
                xmax=coordinates[2]
            elif coordinates[3]>ymin:
                ymax=coordinates[3]
        return xmin, ymin, xmax, ymax


    def update_cards_layout(self, card_layout):
        factset_layout = card_layout[self.first_columnset_index]
        xmin, ymin, xmax, ymax = self.get_factset_coordinates(self.factset_items)
        index_found = ''          
        if  factset_layout.get('object', '')=='columnset':
            rows = factset_layout.get('row', [])
            for index, row in zip(range(len(rows)),rows):
                if row.get('column', {}).get('items', []):
                    if self.factset_items[0]==row.get('column', {}).get('items', [{}])[0]:
                        if not isinstance(index_found, int):
                            index_found = index
                        card_layout[self.first_columnset_index]['row'][index]['column']['items']=self.factset_items
                        factset_card_layout={"object": "factset", "factset":{"items":self.factset_items},"coordinates":[xmin, ymin, xmax, ymax]}
                        card_layout[self.first_columnset_index]['row'][index]['column']['items']=[factset_card_layout]
                        card_layout[self.first_columnset_index]['row'][index]['coordinates']=[xmin, ymin, xmax, ymax]
                        if len(rows)==2:
                            card_layout[self.first_columnset_index]['row']=[card_layout[self.first_columnset_index]['row'][0]]
                            card_layout[self.first_columnset_index]['coordinates']=[xmin, ymin, xmax, ymax]
        # if len(rows)>2:
        #     card_layout[self.first_columnset_index]['row'].pop(index_found)
        return card_layout

    def detect_factset_items(self, design_obj, index=''):
        if isinstance(design_obj, dict):
            if design_obj.get('object', '')=='columnset':
                rows = design_obj.get('row', [])
                if len(rows) >= 2:
                    textbox_item=[]
                    index_flag=0
                    for ind, row in zip(range(len(rows)),rows):
                        if row.get('object', '') == 'column' and len(row['column']['items'])==1:
                            item = row['column']['items'][0]
                            if item.get('object', '')=='textbox':
                                if not isinstance (self.first_columnset_index, int):
                                    self.first_columnset_index = index
                                if index_flag==0:
                                    textbox_item.append(item)
                                elif index_flag==ind:
                                    textbox_item.append(item)
                                    print(textbox_item)
                                else:
                                    textbox_item = []
                                index_flag+=1
                    if len(textbox_item)==2:
                        textbox_item[0].update({'type': 'factset_key'})
                        textbox_item[0].update({'factset_value': textbox_item[1]})
                        textbox_item[1].update({'type': 'factset_value'})
                        if len(self.factset_items)==0:
                            self.first_columnset_index = index
                        self.factset_items.append(textbox_item)             
        elif isinstance(design_obj, list):
            for design, index in zip(design_obj,range(len(design_obj))) :
                self.detect_factset_items(design, index)


class ContainerDetailTemplate:
    """
    This module is responsible for returning the inner design objects for a
    given container from the generated layout structure
    """

    # pylint: disable=no-self-use
    def columnset(self, design_element: Dict) -> List:
        """
        Returns the design objects of a column-set container for the given
        layout structure.
        @param design_element: design element
        @returns: list of elements inside the given row
        """
        return design_element.get("row", [])

    # pylint: disable=no-self-use
    def column(self, design_element: Dict) -> List:
        """
        Returns the design objects of a column container for the given
        layout structure.
        @param design_element: design element
        @returns: list of elements inside the given column
        """
        return design_element.get("column", {}).get("items", [])

    # pylint: disable=no-self-use
    def imageset(self, design_element: Dict) -> List:
        """
        Returns the design objects of a image-set container for the given
        layout structure.
        @param design_element: design element
        @returns: list of elements inside the given image-set
        """
        return design_element.get("imageset", {}).get("items", [])

    # pylint: disable=no-self-use
    def choiceset(self, design_element: Dict) -> List:
        """
        Returns the design objects of a choice-set container for the given
        layout structure.
        @param design_element: design element
        @returns: list of elements inside the given choice-set
        """
        return design_element.get("choiceset", {}).get("items", [])

    def factset(self, design_element: Dict) -> List:
        """
        Returns the design objects of a fact-set container for the given
        layout structure.
        @param design_element: design element
        @returns: list of elements inside the given fact-set
        """
        return design_element.get("factset", {}).get("items", [])
