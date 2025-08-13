module base_plate(){ minkowski(){ translate([0,0,0]) cube([100.0,60.0,5.0], center=true); cylinder(r=3.0,h=0.01); } }

module plate_with_pillar(){ plate_with_pillar(); }

module pillar(){ translate([0,0,0]) cylinder(r=5.0, h=80.0, center=true); }

module final_assembly(){ translate([0,0,0]) rotate([0,0,0]) plate_with_pillar();
linear_extrude(height=10:) { translate([0,0]) circle(r=30.0); } }

module plate_with_pillar(){ union(){ base_plate(); pillar(); } }

translate([0,0,0]) base_plate();
translate([150,0,0]) plate_with_pillar();
translate([300,0,0]) pillar();
translate([450,0,0]) final_assembly();