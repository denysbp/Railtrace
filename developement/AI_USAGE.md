# DUVIDAS

linha: 25 - assigment model:
	ExcludeConstraint(
		("trainset_id", "="),
		(_PERIOD, "&&"),
		name="ex_assignments_trainset_no_overlap",
		using="gist",
	)