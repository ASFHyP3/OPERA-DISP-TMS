from opera_disp_tms.generate_opera_disp_tile import divide_bbox_into_tiles


def test_divide_bbox_into_tiles():
    assert divide_bbox_into_tiles([0, 0, 0, 0]) == []
    assert divide_bbox_into_tiles([1, 1, 1, 1]) == []
    assert divide_bbox_into_tiles([-120, 7, -119, 8]) == [
        [-120, 7, -119, 8]
    ]
    assert divide_bbox_into_tiles([-120, 7, -119, 9]) == [
        [-120, 7, -119, 8],
        [-120, 8, -119, 9]
    ]
    assert divide_bbox_into_tiles([7, -20, 9, -18]) == [
        [7, -20, 8, -19],
        [7, -19, 8, -18],
        [8, -20, 9, -19],
        [8, -19, 9, -18]
    ]
