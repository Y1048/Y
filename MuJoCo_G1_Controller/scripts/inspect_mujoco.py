import mujoco


xml = """
<mujoco>
  <option timestep="0.002" gravity="0 0 -9.81"/>
  <worldbody>
    <body name="box" pos="0 0 1">
      <freejoint/>
      <geom type="box" size="0.1 0.1 0.1"/>
    </body>
  </worldbody>
</mujoco>
"""


model = mujoco.MjModel.from_xml_string(xml)
data = mujoco.MjData(model)

print("MuJoCo model summary")
print("--------------------")
print("nq  (position coordinates):", model.nq)
print("nv  (velocity coordinates):", model.nv)
print("nu  (actuators):", model.nu)
print("njnt (joints):", model.njnt)
print("nbody (bodies):", model.nbody)
print()

print("Joints")
print("------")
for i in range(model.njnt):
    name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
    joint_type = model.jnt_type[i]
    qpos_adr = model.jnt_qposadr[i]
    dof_adr = model.jnt_dofadr[i]
    print(f"{i}: name={name}, type={joint_type}, qpos_adr={qpos_adr}, dof_adr={dof_adr}")

print()
print("Initial state")
print("-------------")
print("qpos:", data.qpos)
print("qvel:", data.qvel)

for _ in range(10):
    mujoco.mj_step(model, data)

print()
print("After 10 simulation steps")
print("-------------------------")
print("qpos:", data.qpos)
print("qvel:", data.qvel)
