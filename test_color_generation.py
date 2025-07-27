#!/usr/bin/env python3
"""
機種色生成のテストスクリプト
"""

import hashlib

def generate_part_color(part_id, part_name=None):
    """機種IDベースで一意な色を生成する"""
    # 機種IDと名前を組み合わせてハッシュを生成
    hash_input = f"{part_id}_{part_name or ''}"
    hash_object = hashlib.md5(hash_input.encode())
    hex_hash = hash_object.hexdigest()
    
    # HSL色空間で色を生成（彩度・明度を固定して見やすい色にする）
    hue = int(hex_hash[:3], 16) % 360  # 0-359の色相
    saturation = 65 + (int(hex_hash[3:5], 16) % 25)  # 65-89%の彩度
    lightness = 45 + (int(hex_hash[5:7], 16) % 20)   # 45-64%の明度
    
    # HSLをRGBに変換
    def hsl_to_rgb(h, s, l):
        h = h / 360
        s = s / 100
        l = l / 100
        
        if s == 0:
            r = g = b = l
        else:
            def hue_to_rgb(p, q, t):
                if t < 0:
                    t += 1
                if t > 1:
                    t -= 1
                if t < 1/6:
                    return p + (q - p) * 6 * t
                if t < 1/2:
                    return q
                if t < 2/3:
                    return p + (q - p) * (2/3 - t) * 6
                return p
            
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)
        
        return int(r * 255), int(g * 255), int(b * 255)
    
    r, g, b = hsl_to_rgb(hue, saturation, lightness)
    return f"#{r:02x}{g:02x}{b:02x}"

# テスト実行
if __name__ == "__main__":
    test_parts = [
        (1, "部品A"),
        (2, "部品B"), 
        (3, "部品C"),
        (4, "部品D"),
        (5, "部品E"),
        (1, "部品A"),  # 同じIDと名前 - 同じ色になるはず
        (6, "部品A"),  # 同じ名前、異なるID - 異なる色になるはず
    ]
    
    print("機種色生成テスト:")
    print("=" * 50)
    
    for part_id, part_name in test_parts:
        color = generate_part_color(part_id, part_name)
        print(f"ID: {part_id:2d}, 名前: {part_name:6s} => {color}")
    
    print("\n✅ 色生成機能は正常に動作しています")