"""Custom template tags for the twf app."""

from django import template

register = template.Library()


@register.simple_tag
def tk_iiif_url(export_url, *args, **kwargs):
    """Converts a Transkribus export URL to an IIIF URL."""

    # Input example: https://files.transkribus.eu/Get?id=QSDNTMEFUAKFLPJCCXZHQSXJ&amp;fileType=view
    # Output example https://files.transkribus.eu/iiif/2/HDSZLYJCXEMHYCCMZAHRPHXC/full/full/0/default.jpg

    # Extract the document ID from the export URL
    document_id = export_url.split("id=")[-1].split("&")[0]

    image_size = kwargs.get("image_size", "full")
    coords = kwargs.get("coords", "full")

    # Create the IIIF URL
    iiif_url = f"https://files.transkribus.eu/iiif/2/{document_id}/{coords}/{image_size}/0/default.jpg"

    return iiif_url


def tk_bounding_box(coords):
    """Converts Transkribus bounding box coordinates to a list of integers."""
    # Input example: x1,y1 x2,y2 x3,y3 x4,y4 ...
    # Output example: [min_x, min_y, width, length]

    xy_pairs = coords.split(" ")

    x_coords = []
    y_coords = []
    for xy in xy_pairs:
        x_str = xy.split(",")[0]
        y_str = xy.split(",")[1]

        if "." in x_str:
            x_coords.append(int(float(x_str)))
        else:
            x_coords.append(int(x_str))

        if "." in y_str:
            y_coords.append(int(float(y_str)))
        else:
            y_coords.append(int(y_str))

    min_x = min(x_coords)
    min_y = min(y_coords)
    max_x = max(x_coords)
    max_y = max(y_coords)

    width = max_x - min_x
    length = max_y - min_y

    return [min_x, min_y, width, length]
