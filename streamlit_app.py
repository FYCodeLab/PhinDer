if start_button:

    raw_names = [
        clean_whitespace(line)
        for line in names_input.splitlines()
        if clean_whitespace(line)
    ]

    if not raw_names:
        st.error("No names provided.")
        st.stop()

    st.session_state.rows = []

    total = len(raw_names)

    st.subheader("Progress")

    progress_bar = st.progress(0)

    status_box = st.empty()

    summary_box = st.empty()

    log_box = st.expander("Live log", expanded=False)

    table_box = st.empty()

    logs = []

    start_time = time.time()

    for index, name in enumerate(raw_names, start=1):

        progress_bar.progress(index / total)

        status_box.info(
            f"Processing {index}/{total} — {name}"
        )

        try:

            rows, total_hits, downloaded = process_name(name)

            if not show_not_found:
                rows = [
                    r for r in rows
                    if r[-1] == "SUCCESS"
                ]

            st.session_state.rows.extend(rows)

            success_count = sum(
                1 for r in rows
                if r[-1] == "SUCCESS"
            )

            logs.append(
                f"✓ {name} | hits={total_hits} | downloaded={downloaded} | added={len(rows)} | success={success_count}"
            )

        except Exception as e:

            first, last = split_asked_name(name)

            st.session_state.rows.append([
                first,
                last,
                "ERROR",
                "ERROR",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "",
                "NON ACCESSIBLE",
                f"ERROR: {e}"
            ])

            logs.append(
                f"✗ {name} | ERROR: {e}"
            )

        df_current = pd.DataFrame(
            st.session_state.rows,
            columns=COLUMNS
        )

        elapsed = round(
            time.time() - start_time,
            1
        )

        success_total = len(
            df_current[
                df_current["Pipeline Status Tracking"] == "SUCCESS"
            ]
        )

        summary_box.markdown(
            f"""
**Processed:** {index}/{total}  
**Rows collected:** {len(df_current)}  
**Successful theses:** {success_total}  
**Elapsed time:** {elapsed} sec
"""
        )

        with log_box:

            st.code(
                "\n".join(logs[-20:]),
                language=None
            )

        table_box.dataframe(
            df_current,
            use_container_width=True,
            height=500
        )

        time.sleep(sleep_time)

    status_box.success(
        f"Completed — {total} names processed"
    )

    progress_bar.progress(1.0)

    df_final = pd.DataFrame(
        st.session_state.rows,
        columns=COLUMNS
    )

    st.divider()

    st.subheader("Final Results")

    st.dataframe(
        df_final,
        use_container_width=True,
        height=700
    )

    st.download_button(
        "Download CSV",
        data=df_final.to_csv(index=False).encode("utf-8-sig"),
        file_name="these_results.csv",
        mime="text/csv"
    )
