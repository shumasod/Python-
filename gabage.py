class GCObject:
    """ガベージコレクション対象のオブジェクト"""
    def __init__(self, name, data=None):
        self.name = name
        self.data = data
        self.references = []  # このオブジェクトが参照しているオブジェクト
        self.ref_count = 0    # このオブジェクトを参照している数
        
    def add_reference(self, obj):
        """他のオブジェクトへの参照を追加"""
        if obj not in self.references:
            self.references.append(obj)
            obj.ref_count += 1
            
    def remove_reference(self, obj):
        """他のオブジェクトへの参照を削除"""
        if obj in self.references:
            self.references.remove(obj)
            obj.ref_count -= 1
            
    def __str__(self):
        return f"Object({self.name}, refs={self.ref_count})"


class SimpleGarbageCollector:
    """シンプルなガベージコレクター"""
    
    def __init__(self):
        self.objects = []  # 管理対象のオブジェクト一覧
        self.root_objects = set()  # ルートオブジェクト（削除されない）
        
    def allocate(self, name, data=None):
        """新しいオブジェクトを作成"""
        obj = GCObject(name, data)
        self.objects.append(obj)
        print(f"✓ オブジェクト '{name}' を作成しました")
        return obj
        
    def add_root(self, obj):
        """ルートオブジェクトとして登録（削除されない）"""
        self.root_objects.add(obj)
        print(f"✓ オブジェクト '{obj.name}' をルートに登録しました")
        
    def remove_root(self, obj):
        """ルートオブジェクトから削除"""
        if obj in self.root_objects:
            self.root_objects.remove(obj)
            print(f"✓ オブジェクト '{obj.name}' をルートから削除しました")
            
    def mark_and_sweep(self):
        """マーク&スイープ方式でガベージコレクション実行"""
        print("\n=== ガベージコレクション開始 ===")
        
        # Step 1: 全オブジェクトを未マークに設定
        for obj in self.objects:
            obj.marked = False
            
        # Step 2: ルートオブジェクトからマーク
        def mark_reachable(obj):
            if hasattr(obj, 'marked') and not obj.marked:
                obj.marked = True
                print(f"  マーク: {obj.name}")
                for ref_obj in obj.references:
                    mark_reachable(ref_obj)
                    
        for root_obj in self.root_objects:
            mark_reachable(root_obj)
            
        # Step 3: マークされていないオブジェクトを削除
        objects_to_remove = []
        for obj in self.objects:
            if not hasattr(obj, 'marked') or not obj.marked:
                objects_to_remove.append(obj)
                
        for obj in objects_to_remove:
            self.objects.remove(obj)
            print(f"  削除: {obj.name}")
            
        print(f"=== ガベージコレクション完了: {len(objects_to_remove)}個のオブジェクトを削除 ===\n")
        
    def reference_counting_gc(self):
        """参照カウント方式でガベージコレクション実行"""
        print("\n=== 参照カウントGC開始 ===")
        
        objects_to_remove = []
        for obj in self.objects:
            if obj.ref_count == 0 and obj not in self.root_objects:
                objects_to_remove.append(obj)
                
        for obj in objects_to_remove:
            # 削除対象オブジェクトが参照しているオブジェクトの参照カウントを減らす
            for ref_obj in obj.references:
                ref_obj.ref_count -= 1
            self.objects.remove(obj)
            print(f"  削除: {obj.name} (参照カウント: 0)")
            
        print(f"=== 参照カウントGC完了: {len(objects_to_remove)}個のオブジェクトを削除 ===\n")
        
    def show_status(self):
        """現在の状態を表示"""
        print("=== 現在のオブジェクト状態 ===")
        for obj in self.objects:
            root_mark = " (ROOT)" if obj in self.root_objects else ""
            refs = [ref.name for ref in obj.references]
            print(f"  {obj.name}: 参照カウント={obj.ref_count}, 参照先={refs}{root_mark}")
        print()


# 使用例とテスト
def demo():
    print("ガベージコレクション デモンストレーション\n")
    
    # ガベージコレクターを作成
    gc = SimpleGarbageCollector()
    
    # オブジェクトを作成
    obj_a = gc.allocate("A", "データA")
    obj_b = gc.allocate("B", "データB")
    obj_c = gc.allocate("C", "データC")
    obj_d = gc.allocate("D", "データD")
    
    # 参照関係を設定
    obj_a.add_reference(obj_b)  # A -> B
    obj_b.add_reference(obj_c)  # B -> C
    obj_c.add_reference(obj_a)  # C -> A (循環参照)
    # obj_d は孤立
    
    # Aをルートオブジェクトに設定
    gc.add_root(obj_a)
    
    print("\n--- 初期状態 ---")
    gc.show_status()
    
    # 参照カウントGCを実行（循環参照があるため、A,B,Cは削除されない）
    gc.reference_counting_gc()
    gc.show_status()
    
    # マーク&スイープGCを実行
    gc.mark_and_sweep()
    gc.show_status()
    
    # ルートからAを削除
    gc.remove_root(obj_a)
    
    # 再度マーク&スイープを実行
    gc.mark_and_sweep()
    gc.show_status()


if __name__ == "__main__":
    demo()
